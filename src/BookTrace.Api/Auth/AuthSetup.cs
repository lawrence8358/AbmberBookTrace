using System.Security.Claims;
using BookTrace.Api.Models;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Identity;

namespace BookTrace.Api.Auth;

public static class AuthPolicies
{
    /// <summary>新增、修改、刪除、借出與歸還等寫入操作：必須已登入。</summary>
    public const string CanEdit = "CanEdit";
}

public sealed record AuthSettings(TimeSpan IdleTimeout);

public static class AuthSetup
{
    public const int MinPasswordLength = 4;
    public const int MaxPasswordLength = 128;

    public static IServiceCollection AddBookTraceAuth(this IServiceCollection services, IConfiguration configuration)
    {
        var idleTimeout = TimeSpan.FromMinutes(configuration.GetValue("Auth:IdleTimeoutMinutes", 60d));
        services.AddSingleton(new AuthSettings(idleTimeout));
        services.AddSingleton<IPasswordHasher<AppUser>, PasswordHasher<AppUser>>();
        services.AddSingleton<LoginThrottle>();

        services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
            .AddCookie(options =>
            {
                options.Cookie.Name = "booktrace.auth";
                options.Cookie.HttpOnly = true;
                options.Cookie.SameSite = SameSiteMode.Strict;
                options.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
                options.ExpireTimeSpan = idleTimeout;
                options.SlidingExpiration = true;
                options.Events.OnRedirectToLogin = context => WriteJsonStatus(
                    context.Response, StatusCodes.Status401Unauthorized, "請先登入，才能進行這項操作。");
                options.Events.OnRedirectToAccessDenied = context => WriteJsonStatus(
                    context.Response, StatusCodes.Status403Forbidden, "沒有權限進行這項操作。");
            });

        services.AddAuthorizationBuilder()
            .AddPolicy(AuthPolicies.CanEdit, policy => policy.RequireAuthenticatedUser());

        return services;
    }

    public static Task SignInAsync(HttpContext http, AppUser user)
    {
        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, user.Id.ToString()),
            new(ClaimTypes.Name, user.UserName),
        };
        var principal = new ClaimsPrincipal(new ClaimsIdentity(claims, CookieAuthenticationDefaults.AuthenticationScheme));
        return http.SignInAsync(
            CookieAuthenticationDefaults.AuthenticationScheme,
            principal,
            new AuthenticationProperties { IsPersistent = false });
    }

    private static Task WriteJsonStatus(HttpResponse response, int statusCode, string message)
    {
        response.StatusCode = statusCode;
        return response.WriteAsJsonAsync(new { message });
    }
}
