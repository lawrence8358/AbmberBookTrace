namespace BookTrace.Api.Models;

public sealed class BorrowingRecord
{
    public int Id { get; set; }
    public int BookId { get; set; }
    public Book Book { get; set; } = null!;
    public string BorrowerName { get; set; } = string.Empty;
    public DateTime BorrowDateUtc { get; set; }
    public DateTime? DueDateUtc { get; set; }
    public DateTime? ReturnedAtUtc { get; set; }
    public string? Note { get; set; }
}
