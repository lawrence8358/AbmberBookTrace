using System.Globalization;
using System.Security.Claims;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Identity;
using Microsoft.EntityFrameworkCore;

namespace BookTrace.Api.Auth;

public sealed record LoginRequest(string? UserName, string? Password);

public sealed record SetupRequest(string? UserName, string? Password);

public sealed record ChangePasswordRequest(string? CurrentPassword, string? NewPassword);

/// <param name="SetupRequired">資料庫裡還沒有任何帳號，畫面要讓使用者建立第一個帳號。</param>
public sealed record SessionResponse(
    bool Authenticated,
    string? UserName,
    bool SetupRequired,
    int IdleTimeoutSeconds);

public static class AuthEndpoints
{
    public const int MaxUserNameLength = 50;

    // 建立第一個帳號時要一個一個來，避免同時送出兩個請求而建立出兩個帳號。
    private static readonly SemaphoreSlim SetupGate = new(1, 1);

    public static void MapAuthEndpoints(this IEndpointRouteBuilder app)
    {
        var auth = app.MapGroup("/api/auth");

        // 沒登入也回 200，前端才不會在每次開啟網站時多一筆錯誤。
        auth.MapGet("/session", SessionAsync);

        auth.MapPost("/setup", SetupAsync);

        auth.MapPost("/login", LoginAsync);

        auth.MapPost("/logout", async (HttpContext http) =>
        {
            await http.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
            return Results.NoContent();
        });

        auth.MapPost("/change-password", ChangePasswordAsync).RequireAuthorization();
    }

    /// <summary>
    /// 只在 Playwright 環境提供：sign-in 確保有一個測試帳號並直接登入，讓既有的瀏覽器流程測試不必每次走登入畫面；
    /// reset 清掉所有帳號，讓「第一次建立帳號」與登入流程的測試可以重複執行。
    /// </summary>
    public static void MapAuthTestEndpoints(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/test/auth/sign-in", async (
            HttpContext http,
            BookDbContext database,
            IPasswordHasher<AppUser> hasher,
            TimeProvider timeProvider,
            CancellationToken cancellationToken) =>
        {
            var user = await database.Users.OrderBy(candidate => candidate.Id).FirstOrDefaultAsync(cancellationToken);
            if (user is null)
            {
                // 這個帳號只用來讓測試略過登入畫面，密碼每次隨機產生，不會有人知道。
                user = NewUser("e2e-tester", Guid.NewGuid().ToString("N"), hasher, timeProvider);
                database.Users.Add(user);
                await database.SaveChangesAsync(cancellationToken);
            }

            await AuthSetup.SignInAsync(http, user);
            return Results.NoContent();
        });

        app.MapPost("/api/test/auth/reset", async (BookDbContext database, CancellationToken cancellationToken) =>
        {
            await database.Users.ExecuteDeleteAsync(cancellationToken);
            return Results.NoContent();
        });
    }

    private static async Task<IResult> SessionAsync(HttpContext http, BookDbContext database, AuthSettings settings, CancellationToken cancellationToken)
    {
        if (http.User.Identity?.IsAuthenticated == true)
        {
            return Results.Ok(new SessionResponse(true, http.User.Identity.Name, false, IdleSeconds(settings)));
        }

        var setupRequired = !await database.Users.AnyAsync(cancellationToken);
        return Results.Ok(new SessionResponse(false, null, setupRequired, IdleSeconds(settings)));
    }

    /// <summary>資料庫裡完全沒有帳號時，讓第一位使用者建立自己的帳號，並直接登入。</summary>
    private static async Task<IResult> SetupAsync(
        SetupRequest request,
        HttpContext http,
        BookDbContext database,
        IPasswordHasher<AppUser> hasher,
        TimeProvider timeProvider,
        AuthSettings settings,
        CancellationToken cancellationToken)
    {
        var userName = request.UserName?.Trim() ?? string.Empty;
        var password = request.Password ?? string.Empty;
        if (userName.Length == 0)
        {
            return Invalid("請輸入帳號。", "userName");
        }

        if (userName.Length > MaxUserNameLength)
        {
            return Invalid($"帳號不能超過 {MaxUserNameLength} 個字。", "userName");
        }

        // 帳號與密碼用「:」分隔傳給 MCP（HTTP Basic），所以帳號不能含有它。
        if (userName.Contains(':'))
        {
            return Invalid("帳號不能包含冒號（:）。", "userName");
        }

        if (PasswordProblem(password) is { } problem)
        {
            return Invalid(problem, "password");
        }

        await SetupGate.WaitAsync(cancellationToken);
        try
        {
            if (await database.Users.AnyAsync(cancellationToken))
            {
                return Results.Json(new { message = "已經有帳號了，請直接登入。" }, statusCode: StatusCodes.Status409Conflict);
            }

            var user = NewUser(userName, password, hasher, timeProvider);
            database.Users.Add(user);
            await database.SaveChangesAsync(cancellationToken);
            await AuthSetup.SignInAsync(http, user);
            return Results.Ok(new SessionResponse(true, user.UserName, false, IdleSeconds(settings)));
        }
        finally
        {
            SetupGate.Release();
        }
    }

    private static async Task<IResult> LoginAsync(
        LoginRequest request,
        HttpContext http,
        BookDbContext database,
        IPasswordHasher<AppUser> hasher,
        LoginThrottle throttle,
        AuthSettings settings,
        CancellationToken cancellationToken)
    {
        if (throttle.IsLocked(out var retryAfter))
        {
            return TooManyAttempts(http, retryAfter);
        }

        var userName = request.UserName?.Trim() ?? string.Empty;
        var user = await database.Users.SingleOrDefaultAsync(candidate => candidate.UserName == userName, cancellationToken);
        var result = user is null
            ? PasswordVerificationResult.Failed
            : hasher.VerifyHashedPassword(user, user.PasswordHash, request.Password ?? string.Empty);
        if (user is null || result == PasswordVerificationResult.Failed)
        {
            throttle.RecordFailure();
            return Results.Json(new { message = "帳號或密碼不正確。" }, statusCode: StatusCodes.Status401Unauthorized);
        }

        throttle.Reset();
        await AuthSetup.SignInAsync(http, user);
        return Results.Ok(new SessionResponse(true, user.UserName, false, IdleSeconds(settings)));
    }

    private static async Task<IResult> ChangePasswordAsync(
        ChangePasswordRequest request,
        HttpContext http,
        BookDbContext database,
        IPasswordHasher<AppUser> hasher,
        LoginThrottle throttle,
        TimeProvider timeProvider,
        AuthSettings settings,
        CancellationToken cancellationToken)
    {
        if (throttle.IsLocked(out var retryAfter))
        {
            return TooManyAttempts(http, retryAfter);
        }

        var userId = int.Parse(http.User.FindFirstValue(ClaimTypes.NameIdentifier)!, CultureInfo.InvariantCulture);
        var user = await database.Users.SingleOrDefaultAsync(candidate => candidate.Id == userId, cancellationToken);
        if (user is null)
        {
            await http.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
            return Results.Json(new { message = "請先登入，才能進行這項操作。" }, statusCode: StatusCodes.Status401Unauthorized);
        }

        var currentPassword = request.CurrentPassword ?? string.Empty;
        if (hasher.VerifyHashedPassword(user, user.PasswordHash, currentPassword) == PasswordVerificationResult.Failed)
        {
            throttle.RecordFailure();
            return Invalid("目前的密碼不正確。", "currentPassword");
        }

        var newPassword = request.NewPassword ?? string.Empty;
        if (PasswordProblem(newPassword) is { } problem)
        {
            return Invalid(problem, "newPassword");
        }

        if (newPassword == currentPassword)
        {
            return Invalid("新密碼不能和目前的密碼相同。", "newPassword");
        }

        throttle.Reset();
        user.PasswordHash = hasher.HashPassword(user, newPassword);
        user.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
        await database.SaveChangesAsync(cancellationToken);

        await AuthSetup.SignInAsync(http, user);
        return Results.Ok(new SessionResponse(true, user.UserName, false, IdleSeconds(settings)));
    }

    private static AppUser NewUser(string userName, string password, IPasswordHasher<AppUser> hasher, TimeProvider timeProvider)
    {
        var user = new AppUser { UserName = userName, UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime };
        user.PasswordHash = hasher.HashPassword(user, password);
        return user;
    }

    private static string? PasswordProblem(string password)
    {
        if (password.Length < AuthSetup.MinPasswordLength)
        {
            return $"密碼至少需要 {AuthSetup.MinPasswordLength} 個字。";
        }

        return password.Length > AuthSetup.MaxPasswordLength
            ? $"密碼不能超過 {AuthSetup.MaxPasswordLength} 個字。"
            : null;
    }

    private static int IdleSeconds(AuthSettings settings) => (int)settings.IdleTimeout.TotalSeconds;

    private static IResult Invalid(string message, string field) =>
        Results.BadRequest(new { message, errors = new Dictionary<string, string> { [field] = message } });

    private static IResult TooManyAttempts(HttpContext http, TimeSpan retryAfter)
    {
        var minutes = Math.Max(1, (int)Math.Ceiling(retryAfter.TotalMinutes));
        http.Response.Headers.RetryAfter = Math.Ceiling(retryAfter.TotalSeconds).ToString(CultureInfo.InvariantCulture);
        return Results.Json(
            new { message = $"嘗試的次數太多了，請約 {minutes} 分鐘後再試。" },
            statusCode: StatusCodes.Status429TooManyRequests);
    }
}
