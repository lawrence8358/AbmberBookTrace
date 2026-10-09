using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;

namespace BookTrace.IntegrationTests;

internal static class TestAuth
{
    public const string UserName = "test-reader";
    public const string Password = "booktrace-test";

    /// <summary>建立（或登入）測試帳號，之後這個 client 就能執行新增、修改、刪除等寫入操作。</summary>
    public static async Task SignInAsync(HttpClient client)
    {
        var response = await client.PostAsJsonAsync("/api/auth/setup", new { userName = UserName, password = Password });
        if (response.StatusCode == HttpStatusCode.Conflict)
        {
            // 同一個測試裡的第二個 client：帳號已經存在，直接登入。
            response = await client.PostAsJsonAsync("/api/auth/login", new { userName = UserName, password = Password });
        }

        response.EnsureSuccessStatusCode();
    }

    /// <summary>MCP 的寫入使用和網站相同的帳號密碼（HTTP Basic）。</summary>
    public static AuthenticationHeaderValue Basic(string userName, string password) =>
        new("Basic", Convert.ToBase64String(Encoding.UTF8.GetBytes($"{userName}:{password}")));

    public sealed record McpToolResult(bool IsError, string Text);

    public static async Task<McpToolResult> McpCallAsync(HttpClient client, string tool, object arguments, AuthenticationHeaderValue? authorization)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, "/mcp");
        request.Headers.Accept.ParseAdd("application/json, text/event-stream");
        request.Headers.Add("MCP-Protocol-Version", "2025-11-25");
        request.Headers.Authorization = authorization;
        request.Content = JsonContent.Create(new { jsonrpc = "2.0", id = 1, method = "tools/call", @params = new { name = tool, arguments } });
        var body = await (await client.SendAsync(request)).Content.ReadAsStringAsync();
        if (body.StartsWith("event:") || body.StartsWith("data:"))
            body = body.Split((char)10).First(line => line.StartsWith("data:")).Substring(5).Trim();
        var result = JsonDocument.Parse(body).RootElement.GetProperty("result");
        var isError = result.TryGetProperty("isError", out var error) && error.GetBoolean();
        var text = string.Join(" ", result.GetProperty("content").EnumerateArray().Select(item => item.GetProperty("text").GetString()));
        return new McpToolResult(isError, text);
    }
}

/// <summary>可以手動往前撥時間的時鐘，用來測試閒置登出與登入鎖定。</summary>
internal sealed class ManualTimeProvider(DateTimeOffset start) : TimeProvider
{
    private DateTimeOffset now = start;

    public override DateTimeOffset GetUtcNow() => now;

    public void Advance(TimeSpan amount) => now += amount;
}
