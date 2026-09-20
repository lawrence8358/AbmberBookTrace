using BookTrace.Api.Models;

namespace BookTrace.Api.Contracts;

public sealed record CreateBookRequest(
    string? Title,
    string? Author,
    string? Isbn,
    string? Publisher,
    string? Category,
    string? Location,
    string? DetailedLocation,
    string? Notes);

public sealed record BookResponse(
    int Id,
    string Title,
    string? Author,
    string? Isbn,
    string? Publisher,
    string? Category,
    string? Location,
    string? DetailedLocation,
    string? Notes,
    string Status,
    DateTime CreatedAtUtc,
    DateTime UpdatedAtUtc)
{
    public static BookResponse From(Book book) => new(
        book.Id,
        book.Title,
        book.Author,
        book.Isbn,
        book.Publisher,
        book.Category,
        book.Location,
        book.DetailedLocation,
        book.Notes,
        book.Status == BookStatus.Home ? "HOME" : "BORROWED",
        book.CreatedAtUtc,
        book.UpdatedAtUtc);
}

public sealed record LibraryStatsResponse(
    int TotalCount,
    int HomeCount,
    int BorrowedCount,
    IReadOnlyList<BookResponse> RecentBooks);
