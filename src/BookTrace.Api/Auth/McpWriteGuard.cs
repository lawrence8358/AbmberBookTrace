using System.Text;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;
using ModelContextProtocol;

namespace BookTrace.Api.Auth;

/// <summary>
/// MCP 的新增、更新、上傳封面使用和網站相同的帳號（<c>Users</c> 資料表）：請求要帶
/// <c>Authorization: Basic base64(帳號:密碼)</c>；讀取工具不需要。規則和網站一致：
/// 密碼錯誤會被擋、連續失敗會暫停。
/// MCP 有自己的失敗計數，設定錯誤的 MCP 客戶端不會把網站登入也鎖住。
/// </summary>
public sealed class McpWriteGuard(IPasswordHasher<AppUser> hasher, TimeProvider timeProvider)
{
    private const string BasicPrefix = "Basic ";
    private readonly LoginThrottle throttle = new(timeProvider);

    public async Task DemandAsync(HttpContext? http, BookDbContext database, CancellationToken cancellationToken)
    {
        if (!TryReadCredentials(http, out var userName, out var password))
        {
            throw new McpException("需要登入：新增或修改書籍時，請在 MCP 客戶端帶上 BookTrace 的帳號與密碼（Authorization: Basic ...）。");
        }

        if (throttle.IsLocked(out var retryAfter))
        {
            var minutes = Math.Max(1, (int)Math.Ceiling(retryAfter.TotalMinutes));
            throw new McpException($"嘗試的次數太多了，請約 {minutes} 分鐘後再試。");
        }

        var user = await database.Users.SingleOrDefaultAsync(candidate => candidate.UserName == userName, cancellationToken);
        if (user is null || hasher.VerifyHashedPassword(user, user.PasswordHash, password) == PasswordVerificationResult.Failed)
        {
            throttle.RecordFailure();
            throw new McpException("帳號或密碼不正確。");
        }

        throttle.Reset();
    }

    private static bool TryReadCredentials(HttpContext? http, out string userName, out string password)
    {
        userName = password = string.Empty;
        var header = http?.Request.Headers.Authorization.ToString() ?? string.Empty;
        if (!header.StartsWith(BasicPrefix, StringComparison.OrdinalIgnoreCase))
        {
            return false;
        }

        string decoded;
        try
        {
            decoded = Encoding.UTF8.GetString(Convert.FromBase64String(header[BasicPrefix.Length..].Trim()));
        }
        catch (FormatException)
        {
            return false;
        }

        var separator = decoded.IndexOf(':');
        if (separator <= 0)
        {
            return false;
        }

        userName = decoded[..separator].Trim();
        password = decoded[(separator + 1)..];
        return userName.Length > 0;
    }
}
