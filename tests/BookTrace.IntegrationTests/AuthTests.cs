using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Xunit;

namespace BookTrace.IntegrationTests;

public sealed class AuthTests : IDisposable
{
    private readonly string root = Path.Combine(Path.GetTempPath(), "booktrace-auth-tests-" + Guid.NewGuid().ToString("N"));
    private readonly ManualTimeProvider clock = new(new DateTimeOffset(2026, 10, 9, 8, 0, 0, TimeSpan.Zero));

    private WebApplicationFactory<global::Program> Api() => new WebApplicationFactory<global::Program>()
        .WithWebHostBuilder(builder =>
        {
            Directory.CreateDirectory(root);
            builder.UseSetting("ConnectionStrings:BookTrace", $"Data Source={Path.Combine(root, "test.db")}");
            builder.UseSetting("CoverStorage:Path", Path.Combine(root, "covers"));
            builder.ConfigureTestServices(services =>
            {
                services.RemoveAll<TimeProvider>();
                services.AddSingleton<TimeProvider>(clock);
                services.PostConfigure<CookieAuthenticationOptions>(
                    CookieAuthenticationDefaults.AuthenticationScheme,
                    options => options.TimeProvider = clock);
            });
        });

    private static Task<HttpResponseMessage> Login(HttpClient client, string password, string? userName = null) =>
        client.PostAsJsonAsync("/api/auth/login", new { userName = userName ?? TestAuth.UserName, password });

    private static Task<HttpResponseMessage> Setup(HttpClient client, string? userName, string? password) =>
        client.PostAsJsonAsync("/api/auth/setup", new { userName, password });

    private static async Task<JsonElement> Session(HttpClient client) =>
        await client.GetFromJsonAsync<JsonElement>("/api/auth/session");

    [Fact]
    public async Task WithoutAnyAccountTheFirstVisitorCreatesOneAndIsSignedIn()
    {
        using var api = Api();
        using var client = api.CreateClient();

        var anonymous = await Session(client);
        Assert.False(anonymous.GetProperty("authenticated").GetBoolean());
        Assert.True(anonymous.GetProperty("setupRequired").GetBoolean());
        Assert.Equal(3600, anonymous.GetProperty("idleTimeoutSeconds").GetInt32());
        Assert.Equal(HttpStatusCode.Unauthorized, (await Login(client, "whatever")).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/books", new { title = "還沒有帳號" })).StatusCode);

        Assert.Equal(HttpStatusCode.BadRequest, (await Setup(client, "  ", "abcd")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await Setup(client, "name:colon", "abcd")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await Setup(client, new string('n', 51), "abcd")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await Setup(client, TestAuth.UserName, "123")).StatusCode);
        Assert.Equal(HttpStatusCode.BadRequest, (await Setup(client, TestAuth.UserName, new string('x', 129))).StatusCode);
        Assert.True((await Session(client)).GetProperty("setupRequired").GetBoolean());

        var created = await Setup(client, $"  {TestAuth.UserName}  ", TestAuth.Password);
        Assert.Equal(HttpStatusCode.OK, created.StatusCode);
        var session = await created.Content.ReadFromJsonAsync<JsonElement>();
        Assert.True(session.GetProperty("authenticated").GetBoolean());
        Assert.Equal(TestAuth.UserName, session.GetProperty("userName").GetString());
        Assert.True((await Session(client)).GetProperty("authenticated").GetBoolean());
        Assert.Equal(HttpStatusCode.Created, (await client.PostAsJsonAsync("/api/books", new { title = "建立帳號後" })).StatusCode);

        // 已經有帳號之後，任何人都不能再建立新的帳號。
        using var stranger = api.CreateClient();
        Assert.Equal(HttpStatusCode.Conflict, (await Setup(stranger, "someone-else", "abcd")).StatusCode);
        Assert.False((await Session(stranger)).GetProperty("setupRequired").GetBoolean());
    }

    [Fact]
    public async Task OnlyOneAccountIsCreatedWhenSetupsArriveTogether()
    {
        using var api = Api();
        using var client = api.CreateClient();
        var responses = await Task.WhenAll(Enumerable.Range(0, 5).Select(number =>
            Task.Run(() => Setup(client, $"user-{number}", "abcd"))));

        Assert.Single(responses, response => response.StatusCode == HttpStatusCode.OK);
        Assert.Equal(4, responses.Count(response => response.StatusCode == HttpStatusCode.Conflict));
    }

    [Fact]
    public async Task LoginAndLogoutWorkAndUserNameIgnoresCase()
    {
        using var api = Api();
        using var client = api.CreateClient();
        await TestAuth.SignInAsync(client);

        Assert.Equal(HttpStatusCode.NoContent, (await client.PostAsync("/api/auth/logout", null)).StatusCode);
        Assert.False((await Session(client)).GetProperty("authenticated").GetBoolean());
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/books", new { title = "已登出" })).StatusCode);

        Assert.Equal(HttpStatusCode.Unauthorized, (await Login(client, "wrong-password")).StatusCode);
        Assert.Equal(HttpStatusCode.Unauthorized, (await Login(client, TestAuth.Password, "someone-else")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await Login(client, TestAuth.Password, TestAuth.UserName.ToUpperInvariant())).StatusCode);
        Assert.Equal(HttpStatusCode.Created, (await client.PostAsJsonAsync("/api/books", new { title = "重新登入" })).StatusCode);
    }

    [Fact]
    public async Task ChangingThePasswordNeedsTheCurrentOneAndReplacesIt()
    {
        using var api = Api();
        using var client = api.CreateClient();
        await TestAuth.SignInAsync(client);

        async Task<HttpStatusCode> Change(string current, string next) =>
            (await client.PostAsJsonAsync("/api/auth/change-password", new { currentPassword = current, newPassword = next })).StatusCode;

        Assert.Equal(HttpStatusCode.BadRequest, await Change("nope", "abcd"));
        Assert.Equal(HttpStatusCode.BadRequest, await Change(TestAuth.Password, "123"));
        Assert.Equal(HttpStatusCode.BadRequest, await Change(TestAuth.Password, TestAuth.Password));
        Assert.Equal(HttpStatusCode.BadRequest, await Change(TestAuth.Password, new string('x', 129)));
        Assert.Equal(HttpStatusCode.OK, await Change(TestAuth.Password, "abcd"));
        Assert.Equal(HttpStatusCode.Created, (await client.PostAsJsonAsync("/api/books", new { title = "換完密碼" })).StatusCode);

        using var other = api.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await Login(other, TestAuth.Password)).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await Login(other, "abcd")).StatusCode);

        using var anonymous = api.CreateClient();
        Assert.Equal(HttpStatusCode.Unauthorized, (await anonymous.PostAsJsonAsync("/api/auth/change-password", new { currentPassword = "abcd", newPassword = "efgh" })).StatusCode);
    }

    [Fact]
    public async Task EveryWriteEndpointRequiresLoginWhileReadsStayOpen()
    {
        using var api = Api();
        using var client = api.CreateClient();
        using var form = new MultipartFormDataContent { { new ByteArrayContent([1]), "cover", "cover.png" } };

        var writes = new (string Method, string Url, HttpContent? Body)[]
        {
            ("POST", "/api/books", JsonContent.Create(new { title = "x" })),
            ("PUT", "/api/books/1", JsonContent.Create(new { title = "x" })),
            ("DELETE", "/api/books/1", null),
            ("POST", "/api/books/1/borrow", JsonContent.Create(new { borrowerName = "x" })),
            ("POST", "/api/books/1/return", null),
            ("POST", "/api/books/1/cover", form),
            ("DELETE", "/api/books/1/cover", null),
            ("POST", "/api/recycle-bin/1/restore", null),
        };
        foreach (var (method, url, body) in writes)
        {
            using var request = new HttpRequestMessage(new HttpMethod(method), url) { Content = body };
            var response = await client.SendAsync(request);
            Assert.True(response.StatusCode == HttpStatusCode.Unauthorized, $"{method} {url} 回傳 {(int)response.StatusCode}");
        }

        foreach (var url in new[] { "/api/books", "/api/books/stats", "/api/borrowings", "/api/reminders", "/api/recycle-bin" })
        {
            Assert.Equal(HttpStatusCode.OK, (await client.GetAsync(url)).StatusCode);
        }
    }

    [Fact]
    public async Task SessionEndsAfterAnHourWithoutActivity()
    {
        using var api = Api();
        using var client = api.CreateClient();
        await TestAuth.SignInAsync(client);

        clock.Advance(TimeSpan.FromMinutes(59));
        Assert.True((await Session(client)).GetProperty("authenticated").GetBoolean());

        // 剛才 59 分鐘時有活動，所以一個小時要從那時候重新算。
        clock.Advance(TimeSpan.FromMinutes(61));
        Assert.False((await Session(client)).GetProperty("authenticated").GetBoolean());
        Assert.Equal(HttpStatusCode.Unauthorized, (await client.PostAsJsonAsync("/api/books", new { title = "閒置太久" })).StatusCode);
    }

    [Fact]
    public async Task SessionStaysSignedInForAsLongAsThereIsActivity()
    {
        using var api = Api();
        using var client = api.CreateClient();
        await TestAuth.SignInAsync(client);

        for (var minutes = 40; minutes <= 160; minutes += 40)
        {
            clock.Advance(TimeSpan.FromMinutes(40));
            Assert.True((await Session(client)).GetProperty("authenticated").GetBoolean(), $"持續使用 {minutes} 分鐘後應該仍是登入狀態");
        }

        Assert.Equal(HttpStatusCode.Created, (await client.PostAsJsonAsync("/api/books", new { title = "一直在用" })).StatusCode);
    }

    [Fact]
    public async Task LoginIsLockedAfterFiveFailuresUntilTheWaitIsOver()
    {
        using var api = Api();
        using (var owner = api.CreateClient())
        {
            await TestAuth.SignInAsync(owner);
        }

        using var client = api.CreateClient();
        for (var i = 0; i < 5; i++)
        {
            Assert.Equal(HttpStatusCode.Unauthorized, (await Login(client, "wrong")).StatusCode);
        }

        var locked = await Login(client, TestAuth.Password);
        Assert.Equal(HttpStatusCode.TooManyRequests, locked.StatusCode);
        Assert.NotNull(locked.Headers.RetryAfter);

        clock.Advance(TimeSpan.FromMinutes(5).Add(TimeSpan.FromSeconds(1)));
        Assert.Equal(HttpStatusCode.OK, (await Login(client, TestAuth.Password)).StatusCode);
    }

    [Fact]
    public async Task McpLoginFailuresLockMcpWritesWithoutLockingTheWebsiteLogin()
    {
        using var api = Api();
        using var site = api.CreateClient();
        await TestAuth.SignInAsync(site);
        using var mcp = api.CreateClient();
        var wrong = TestAuth.Basic(TestAuth.UserName, "wrong-password");
        var right = TestAuth.Basic(TestAuth.UserName, TestAuth.Password);

        for (var i = 0; i < 5; i++)
        {
            Assert.True((await TestAuth.McpCallAsync(mcp, "add_book", new { title = "x" }, wrong)).IsError);
        }

        var locked = await TestAuth.McpCallAsync(mcp, "add_book", new { title = "鎖定中" }, right);
        Assert.True(locked.IsError);
        Assert.Contains("嘗試的次數太多", locked.Text);
        Assert.Equal(HttpStatusCode.OK, (await Login(site, TestAuth.Password)).StatusCode);

        clock.Advance(TimeSpan.FromMinutes(5).Add(TimeSpan.FromSeconds(1)));
        Assert.False((await TestAuth.McpCallAsync(mcp, "add_book", new { title = "解除後" }, right)).IsError);
    }

    public void Dispose()
    {
        Microsoft.Data.Sqlite.SqliteConnection.ClearAllPools();
        if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
    }
}
