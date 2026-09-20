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

public sealed record BorrowBookRequest(
    string? BorrowerName,
    DateOnly? DueDate,
    string? Note,
    bool ClearDueDate = false);

public sealed record BorrowingRecordResponse(
    int Id,
    string BorrowerName,
    DateTime BorrowDateUtc,
    DateOnly? DueDate,
    DateTime? ReturnedAtUtc,
    string? Note)
{
    public static BorrowingRecordResponse From(BorrowingRecord record) => new(
        record.Id,
        record.BorrowerName,
        record.BorrowDateUtc,
        record.DueDateUtc is null ? null : DateOnly.FromDateTime(record.DueDateUtc.Value),
        record.ReturnedAtUtc,
        record.Note);
}

public sealed record BorrowingHistoryResponse(
    int Id,
    int BookId,
    string BookTitle,
    string? BookAuthor,
    string? CoverUrl,
    string BorrowerName,
    DateTime BorrowDateUtc,
    DateOnly? DueDate,
    DateTime? ReturnedAtUtc,
    string? Note,
    string Status)
{
    public static BorrowingHistoryResponse From(BorrowingRecord record) => new(
        record.Id,
        record.BookId,
        record.Book.Title,
        record.Book.Author,
        record.Book.CoverImageData is null
            ? null
            : $"/api/books/{record.BookId}/cover?v={record.Book.UpdatedAtUtc.Ticks}",
        record.BorrowerName,
        record.BorrowDateUtc,
        record.DueDateUtc is null ? null : DateOnly.FromDateTime(record.DueDateUtc.Value),
        record.ReturnedAtUtc,
        record.Note,
        record.ReturnedAtUtc is null ? "CURRENT" : "RETURNED");
}

public sealed record BorrowingReminderResponse(
    int BorrowingRecordId,
    int BookId,
    string BookTitle,
    string? BookAuthor,
    string? CoverUrl,
    string BorrowerName,
    DateOnly DueDate,
    string ReminderType,
    int DaysOverdue)
{
    public static BorrowingReminderResponse From(BorrowingRecord record, DateOnly today) =>
        new(
            record.Id,
            record.BookId,
            record.Book.Title,
            record.Book.Author,
            record.Book.CoverImageData is null
                ? null
                : $"/api/books/{record.BookId}/cover?v={record.Book.UpdatedAtUtc.Ticks}",
            record.BorrowerName,
            DateOnly.FromDateTime(record.DueDateUtc!.Value),
            DateOnly.FromDateTime(record.DueDateUtc.Value) < today ? "OVERDUE" : "DUE_TODAY",
            DateOnly.FromDateTime(record.DueDateUtc.Value) < today
                ? today.DayNumber - DateOnly.FromDateTime(record.DueDateUtc.Value).DayNumber
                : 0);
}

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
    string? CoverUrl,
    string Status,
    DateTime CreatedAtUtc,
    DateTime UpdatedAtUtc,
    BorrowingRecordResponse? CurrentBorrowing)
{
    public static BookResponse From(Book book, BorrowingRecord? currentBorrowing = null) => new(
        book.Id,
        book.Title,
        book.Author,
        book.Isbn,
        book.Publisher,
        book.Category,
        book.Location,
        book.DetailedLocation,
        book.Notes,
        book.CoverImageData is null ? null : $"/api/books/{book.Id}/cover?v={book.UpdatedAtUtc.Ticks}",
        book.Status == BookStatus.Home ? "HOME" : "BORROWED",
        book.CreatedAtUtc,
        book.UpdatedAtUtc,
        currentBorrowing is null ? null : BorrowingRecordResponse.From(currentBorrowing));
}

public sealed record LibraryStatsResponse(
    int TotalCount,
    int HomeCount,
    int BorrowedCount,
    IReadOnlyList<BookResponse> RecentBooks);
