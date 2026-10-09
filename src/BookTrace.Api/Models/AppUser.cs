namespace BookTrace.Api.Models;

public sealed class AppUser
{
    public int Id { get; set; }
    public string UserName { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
    public DateTime UpdatedAtUtc { get; set; }
}
