namespace BookTrace.Api.Models;

public enum BookStatus
{
    Home,
    Borrowed,
}

public sealed class Book
{
    public int Id { get; set; }
    public string Title { get; set; } = string.Empty;
    public string? Author { get; set; }
    public string? Isbn { get; set; }
    public string? Publisher { get; set; }
    public string? Category { get; set; }
    public string? Location { get; set; }
    public string? DetailedLocation { get; set; }
    public string? Notes { get; set; }
    public BookStatus Status { get; set; } = BookStatus.Home;
    public DateTime CreatedAtUtc { get; set; }
    public DateTime UpdatedAtUtc { get; set; }
    public ICollection<BorrowingRecord> BorrowingRecords { get; set; } = new List<BorrowingRecord>();
}
