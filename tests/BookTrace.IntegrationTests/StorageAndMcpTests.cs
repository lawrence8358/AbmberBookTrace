using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using BookTrace.Mcp;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Xunit;

namespace BookTrace.IntegrationTests;

public sealed class StorageAndMcpTests : IDisposable
{
    private readonly string root = Path.Combine(Path.GetTempPath(), "booktrace-tests-" + Guid.NewGuid().ToString("N"));
    private static readonly byte[] Png = Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=");

    private WebApplicationFactory<global::Program> Api() => new WebApplicationFactory<global::Program>()
        .WithWebHostBuilder(builder =>
        {
            Directory.CreateDirectory(root);
            builder.UseSetting("ConnectionStrings:BookTrace", $"Data Source={Path.Combine(root, "test.db")}");
            builder.UseSetting("CoverStorage:Path", Path.Combine(root, "covers"));
        });

    [Fact]
    public async Task CoversUseFilesAndConditionalCachingAndAreDeletedAfterExpiry()
    {
        using var api = Api();
        using var client = api.CreateClient();
        var created = await client.PostAsJsonAsync("/api/books", new { title = "封面測試" });
        var id = (await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetInt32();
        async Task<string> Upload()
        {
            using var form = new MultipartFormDataContent();
            var image = new ByteArrayContent(Png);
            image.Headers.ContentType = new("image/png");
            form.Add(image, "cover", "../../cover.png");
            var response = await client.PostAsync($"/api/books/{id}/cover", form);
            response.EnsureSuccessStatusCode();
            return (await response.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("coverUrl").GetString()!;
        }
        var first = await Upload();
        var cover = await client.GetAsync(first);
        Assert.Equal(Png, await cover.Content.ReadAsByteArrayAsync());
        Assert.Contains("immutable", cover.Headers.CacheControl!.ToString());
        using var conditional = new HttpRequestMessage(HttpMethod.Get, first);
        conditional.Headers.IfNoneMatch.Add(cover.Headers.ETag!);
        Assert.Equal(HttpStatusCode.NotModified, (await client.SendAsync(conditional)).StatusCode);
        var second = await Upload();
        Assert.NotEqual(first, second);
        Assert.False(File.Exists(Path.Combine(root, first.TrimStart('/'))));
        using (var scope = api.Services.CreateScope())
        {
            var database = scope.ServiceProvider.GetRequiredService<BookDbContext>();
            var book = await database.Books.FindAsync(id);
            Assert.NotNull(book!.CoverStorageName);
        }
        Assert.Equal(HttpStatusCode.NoContent, (await client.DeleteAsync($"/api/books/{id}/cover")).StatusCode);
        Assert.Empty(Directory.GetFiles(Path.Combine(root, "covers")));
        await Upload();
        await client.DeleteAsync($"/api/books/{id}");
        Assert.Single(Directory.GetFiles(Path.Combine(root, "covers")));
        using (var scope = api.Services.CreateScope())
        {
            var database = scope.ServiceProvider.GetRequiredService<BookDbContext>();
            (await database.Books.FindAsync(id))!.DeletedAtUtc = DateTime.UtcNow.AddDays(-31);
            await database.SaveChangesAsync();
        }
        await client.GetAsync("/api/books");
        Assert.Empty(Directory.GetFiles(Path.Combine(root, "covers")));
    }

    [Fact]
    public async Task FileCoverSurvivesRestart()
    {
        using (var api = Api())
        {
            using var client = api.CreateClient();
            var created = await client.PostAsJsonAsync("/api/books", new { title = "持久化封面" });
            var id = (await created.Content.ReadFromJsonAsync<JsonElement>()).GetProperty("id").GetInt32();
            using var form = new MultipartFormDataContent();
            var image = new ByteArrayContent(Png);
            image.Headers.ContentType = new("image/png");
            form.Add(image, "cover", "cover.png");
            (await client.PostAsync($"/api/books/{id}/cover", form)).EnsureSuccessStatusCode();
        }
        string? url = null;
        for (var i = 0; i < 2; i++)
        {
            using var api = Api();
            using var client = api.CreateClient();
            var books = await client.GetFromJsonAsync<JsonElement>("/api/books");
            var current = books[0].GetProperty("coverUrl").GetString();
            if (url is not null) Assert.Equal(url, current);
            url = current;
            Assert.Equal(Png, await client.GetByteArrayAsync(url));
            Assert.Single(Directory.GetFiles(Path.Combine(root, "covers")));
        }
    }

    [Fact]
    public async Task McpDisabledHasNoEndpoint()
    {
        using var server = Api().WithWebHostBuilder(builder => builder.UseSetting("Mcp:Enabled", "false"));
        using var client = server.CreateClient();
        Assert.Equal(HttpStatusCode.NotFound, (await client.PostAsJsonAsync("/mcp", new { })).StatusCode);
    }

    [Fact]
    public async Task HttpMcpListsToolsFindsBooksAndAddsWithoutDuplicates()
    {
        using var api = Api();
        using var apiClient = api.CreateClient();
        using var client = api.CreateClient();
        async Task<JsonElement> Rpc(string method, object parameters)
        {
            using var request = new HttpRequestMessage(HttpMethod.Post, "/mcp");
            request.Headers.Accept.ParseAdd("application/json, text/event-stream");
            request.Headers.Add("MCP-Protocol-Version", "2025-11-25");
            request.Content = JsonContent.Create(new { jsonrpc = "2.0", id = 1, method, @params = parameters });
            var response = await client.SendAsync(request);
            var body = await response.Content.ReadAsStringAsync();
            Assert.True(response.IsSuccessStatusCode, body);
            if (body.StartsWith("event:") || body.StartsWith("data:"))
                body = body.Split('\n').First(line => line.StartsWith("data:")).Substring(5).Trim();
            return JsonDocument.Parse(body).RootElement.Clone();
        }
        var initialize = await Rpc("initialize", new { protocolVersion = "2025-11-25", capabilities = new { }, clientInfo = new { name = "tests", version = "1.0" } });
        Assert.True(initialize.TryGetProperty("result", out _), initialize.ToString());
        var tools = await Rpc("tools/list", new { });
        Assert.Equal(6, tools.GetProperty("result").GetProperty("tools").GetArrayLength());
        var added = await Rpc("tools/call", new { name = "add_book", arguments = new { title = "MCP 測試", author = "作者", isbn = "978-1234567890", notes = "測試筆記", publicationDate = "2020-02-29", purchaseDate = "2026-09-28" } });
        Assert.True(ToolResult(added).GetProperty("created").GetBoolean());
        var repeated = await Rpc("tools/call", new { name = "add_book", arguments = new { title = "另一個名稱", isbn = "978 1234567890" } });
        Assert.False(ToolResult(repeated).GetProperty("created").GetBoolean());
        var found = await Rpc("tools/call", new { name = "find_book", arguments = new { isbn = "9781234567890" } });
        Assert.True(ToolResult(found).GetProperty("exists").GetBoolean());
        var listed = ToolResult(await Rpc("tools/call", new { name = "list_books", arguments = new { search = "MCP" } }));
        Assert.Equal(1, listed.GetArrayLength());
        var id = listed[0].GetProperty("id").GetInt32();
        var detail = ToolResult(await Rpc("tools/call", new { name = "get_book", arguments = new { id } }));
        Assert.Equal("作者", detail.GetProperty("author").GetString());
        Assert.Equal("2020-02-29", detail.GetProperty("publicationDate").GetString());
        Assert.Equal("2026-09-28", detail.GetProperty("purchaseDate").GetString());
        var updated = ToolResult(await Rpc("tools/call", new { name = "update_book", arguments = new { id, publisher = "出版社", notes = "不可覆蓋", purchaseDate = "2026-01-01" } }));
        Assert.Equal("出版社", updated.GetProperty("publisher").GetString());
        Assert.Equal("測試筆記", updated.GetProperty("notes").GetString());
        Assert.Equal("2026-09-28", updated.GetProperty("purchaseDate").GetString());
        var cover = ToolResult(await Rpc("tools/call", new { name = "upload_book_cover", arguments = new { id, imageBase64 = Convert.ToBase64String(Png), contentType = "image/png" } }));
        Assert.Equal(Png, await client.GetByteArrayAsync(cover.GetProperty("coverUrl").GetString()));
        var badImage = await Rpc("tools/call", new { name = "upload_book_cover", arguments = new { id, imageBase64 = Convert.ToBase64String("not an image"u8), contentType = "image/png" } });
        Assert.True(badImage.GetProperty("result").GetProperty("isError").GetBoolean());
        var badDate = await Rpc("tools/call", new { name = "update_book", arguments = new { id, publicationDate = "2025-02-29", fillMissingOnly = false } });
        Assert.True(badDate.GetProperty("result").GetProperty("isError").GetBoolean());
        var sameTitle = ToolResult(await Rpc("tools/call", new { name = "add_book", arguments = new { title = " MCP 測試 ", author = "作者" } }));
        Assert.False(sameTitle.GetProperty("created").GetBoolean());
        var invalid = await Rpc("tools/call", new { name = "add_book", arguments = new { title = " " } });
        Assert.True(invalid.GetProperty("result").GetProperty("isError").GetBoolean());
        var books = await apiClient.GetFromJsonAsync<JsonElement>("/api/books");
        Assert.Equal(1, books.GetArrayLength());
        Assert.Equal("測試筆記", books[0].GetProperty("notes").GetString());
        await apiClient.DeleteAsync($"/api/books/{id}");
        Assert.False(ToolResult(await Rpc("tools/call", new { name = "find_book", arguments = new { isbn = "9781234567890" } })).GetProperty("exists").GetBoolean());
    }

    [Fact]
    public async Task ApiDatesCanBeEditedAndClearedWithoutTimezoneConversion()
    {
        using var api = Api();
        using var client = api.CreateClient();
        var response = await client.PostAsJsonAsync("/api/books", new { title = "日期測試", publicationDate = "2000-02-29", purchaseDate = "2026-01-01" });
        var book = await response.Content.ReadFromJsonAsync<JsonElement>();
        var id = book.GetProperty("id").GetInt32();
        Assert.Equal("2000-02-29", book.GetProperty("publicationDate").GetString());
        response = await client.PutAsJsonAsync($"/api/books/{id}", new { title = "日期測試", publicationDate = "2024-12-31", purchaseDate = (string?)null });
        book = await response.Content.ReadFromJsonAsync<JsonElement>();
        Assert.Equal("2024-12-31", book.GetProperty("publicationDate").GetString());
        Assert.Equal(JsonValueKind.Null, book.GetProperty("purchaseDate").ValueKind);
        response = await client.PutAsJsonAsync($"/api/books/{id}", new { title = "日期測試", publicationDate = "2025-02-29" });
        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);
        book = await client.GetFromJsonAsync<JsonElement>($"/api/books/{id}");
        Assert.Equal("2024-12-31", book.GetProperty("publicationDate").GetString());
    }

    [Fact]
    public async Task ConcurrentAddRequestsCreateOnlyOneBook()
    {
        using var api = Api();
        using var client = api.CreateClient();
        var responses = await Task.WhenAll(Enumerable.Range(0, 5).Select(_ =>
            Task.Run(() => client.PostAsJsonAsync("/api/books", new { title = "同時新增", isbn = "9781234567890", skipIfExists = true }))));
        Assert.All(responses, response => Assert.True(response.IsSuccessStatusCode));
        Assert.Single(responses, response => response.StatusCode == HttpStatusCode.Created);
        Assert.Equal(1, (await client.GetFromJsonAsync<JsonElement>("/api/books")).GetArrayLength());
    }

    public void Dispose()
    {
        Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
    }

    private static JsonElement ToolResult(JsonElement response)
    {
        var result = response.GetProperty("result");
        Assert.False(result.TryGetProperty("isError", out var error) && error.GetBoolean(), response.ToString());
        return JsonDocument.Parse(result.GetProperty("content")[0].GetProperty("text").GetString()!).RootElement.Clone();
    }
}
