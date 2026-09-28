using BookTrace.Api.Contracts;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using BookTrace.Api.Storage;
using Microsoft.EntityFrameworkCore;

namespace BookTrace.Api.Services;

public static class BookOperations
{
    private const long MaxCoverSizeBytes = 5 * 1024 * 1024;
    private static string? TrimToNull(string? value) => string.IsNullOrWhiteSpace(value) ? null : value.Trim();

    public static async Task<IResult> ListAsync(
        string? search,
        string? status,
        BookDbContext database,
        CancellationToken cancellationToken)
    {
        var booksQuery = database.Books
            .AsNoTracking()
            .Where(book => !book.IsDeleted);
        var normalizedSearch = search?.Trim().ToLowerInvariant();

        if (!string.IsNullOrEmpty(normalizedSearch))
        {
            booksQuery = booksQuery.Where(book =>
                book.Title.ToLower().Contains(normalizedSearch)
                || (book.Author != null && book.Author.ToLower().Contains(normalizedSearch))
                || (book.Isbn != null && book.Isbn.ToLower().Contains(normalizedSearch)));
        }

        if (!string.IsNullOrWhiteSpace(status)
            && !status.Equals("ALL", StringComparison.OrdinalIgnoreCase))
        {
            if (!Enum.TryParse<BookStatus>(status, ignoreCase: true, out var requestedStatus))
            {
                return Results.BadRequest(new { message = "無法辨識這個書籍狀態篩選。" });
            }

            booksQuery = booksQuery.Where(book => book.Status == requestedStatus);
        }

        var books = await booksQuery
            .Select(book => new
            {
                Book = book,
                HasAuthor = book.Author != null && book.Author != "",
                AuthorCount = book.Author == null
                    ? 0
                    : database.Books.Count(candidate => !candidate.IsDeleted && candidate.Author == book.Author),
            })
            .OrderByDescending(book => book.HasAuthor)
            .ThenByDescending(book => book.AuthorCount)
            .ThenBy(book => book.Book.Title.ToLower())
            .ThenBy(book => book.Book.Id)
            .Select(book => BookResponse.From(book.Book))
            .ToListAsync(cancellationToken);

        return Results.Ok(books);
    }

    public static async Task<IResult> GetAsync(
        int id,
        BookDbContext database,
        CancellationToken cancellationToken)
    {
        var book = await database.Books
            .AsNoTracking()
            .Include(candidate => candidate.BorrowingRecords
                .Where(record => record.ReturnedAtUtc == null))
            .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);

        return book is null
            ? Results.NotFound(new { message = "找不到這本書。" })
            : Results.Ok(BookResponse.From(book, book.BorrowingRecords.SingleOrDefault()));
    }

    public static async Task<IResult> CreateAsync(
        CreateBookRequest request,
        BookDbContext database,
        TimeProvider timeProvider,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Title))
        {
            return Results.BadRequest(new
            {
                message = "請輸入書名，才能保存這本書。",
                errors = new { title = "書名是必填欄位。" },
            });
        }

        // SQLite takes the write lock before the duplicate check, including across API instances.
        await using var transaction = await database.Database.BeginTransactionAsync(cancellationToken);
        if (request.SkipIfExists)
        {
            var candidates = await database.Books.AsNoTracking().Where(book => !book.IsDeleted).ToListAsync(cancellationToken);
            var existing = candidates.FirstOrDefault(book =>
                (!string.IsNullOrWhiteSpace(request.Isbn) && NormalizeIsbn(book.Isbn) == NormalizeIsbn(request.Isbn))
                || (string.Equals(book.Title.Trim(), request.Title.Trim(), StringComparison.OrdinalIgnoreCase)
                    && string.Equals(book.Author?.Trim() ?? "", request.Author?.Trim() ?? "", StringComparison.OrdinalIgnoreCase)));
            if (existing is not null) return Results.Ok(BookResponse.From(existing));
        }

        var now = timeProvider.GetUtcNow().UtcDateTime;
        var book = new Book
        {
            Status = BookStatus.Home,
            CreatedAtUtc = now,
            UpdatedAtUtc = now,
        };
        ApplyBookFields(book, request.Title, request.Author, request.Isbn, request.Publisher,
            request.Category, request.Location, request.DetailedLocation, request.Notes);
        book.PublicationDate = request.PublicationDate;
        book.PurchaseDate = request.PurchaseDate;

        database.Books.Add(book);
        await database.SaveChangesAsync(cancellationToken);
        await transaction.CommitAsync(cancellationToken);

        return Results.Created($"/api/books/{book.Id}", BookResponse.From(book));
    }

    public static async Task<IResult> UpdateAsync(
        int id,
        UpdateBookRequest request,
        BookDbContext database,
        TimeProvider timeProvider,
        CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(request.Title))
        {
            return Results.BadRequest(new
            {
                message = "請輸入書名，才能保存這本書。",
                errors = new { title = "書名是必填欄位。" },
            });
        }

        var book = await database.Books
            .Include(candidate => candidate.BorrowingRecords)
            .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
        if (book is null)
        {
            return Results.NotFound(new { message = "找不到這本書。" });
        }

        ApplyBookFields(book, request.Title, request.Author, request.Isbn, request.Publisher,
            request.Category, request.Location, request.DetailedLocation, request.Notes);
        book.PublicationDate = request.PublicationDate;
        book.PurchaseDate = request.PurchaseDate;
        book.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;

        await database.SaveChangesAsync(cancellationToken);

        return Results.Ok(BookResponse.From(
            book,
            book.BorrowingRecords.SingleOrDefault(record => record.ReturnedAtUtc == null)));
    }

    public static async Task<IResult> UploadCoverAsync(
        int id,
        IFormFile? cover,
        BookDbContext database,
        CoverStorage storage,
        TimeProvider timeProvider,
        CancellationToken cancellationToken)
    {
        if (cover is null)
        {
            return Results.BadRequest(new
            {
                message = "請選擇一張封面圖片。",
                errors = new { cover = "請選擇一張封面圖片。" },
            });
        }

        var upload = await ReadCoverAsync(cover, cancellationToken);
        if (upload.Error is not null)
        {
            return Results.BadRequest(new
            {
                message = upload.Error,
                errors = new { cover = upload.Error },
            });
        }

        var book = await database.Books
            .Include(candidate => candidate.BorrowingRecords
                .Where(record => record.ReturnedAtUtc == null))
            .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
        if (book is null)
        {
            return Results.NotFound(new { message = "找不到這本書。" });
        }

        var oldName = book.CoverStorageName;
        book.CoverStorageName = await storage.WriteAsync(upload.Content!, upload.ContentType!, cancellationToken);
        book.CoverContentType = upload.ContentType;
        book.CoverFileName = Path.GetFileName(cover.FileName);
        book.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
        await database.SaveChangesAsync(cancellationToken);
        storage.Delete(oldName);

        return Results.Ok(BookResponse.From(
            book,
            book.BorrowingRecords.SingleOrDefault()));
    }

    static string NormalizeIsbn(string? value) =>
        new string((value ?? "").Where(character => !char.IsWhiteSpace(character) && character != '-').ToArray()).ToUpperInvariant();

    static void ApplyBookFields(
        Book book,
        string? title,
        string? author,
        string? isbn,
        string? publisher,
        string? category,
        string? location,
        string? detailedLocation,
        string? notes)
    {
        book.Title = title?.Trim() ?? string.Empty;
        book.Author = TrimToNull(author);
        book.Isbn = TrimToNull(isbn);
        book.Publisher = TrimToNull(publisher);
        book.Category = TrimToNull(category);
        book.Location = TrimToNull(location);
        book.DetailedLocation = TrimToNull(detailedLocation);
        book.Notes = TrimToNull(notes);
    }

    static async Task<CoverUploadResult> ReadCoverAsync(
        IFormFile cover,
        CancellationToken cancellationToken)
    {
        if (cover.Length <= 0)
        {
            return CoverUploadResult.Invalid("封面圖片不可為空白檔案。");
        }

        if (cover.Length > MaxCoverSizeBytes)
        {
            return CoverUploadResult.Invalid("封面圖片不可超過 5 MB。");
        }

        var contentType = cover.ContentType.Trim().ToLowerInvariant();
        if (!IsSupportedCoverType(contentType))
        {
            return CoverUploadResult.Invalid("封面只接受 JPG、PNG、GIF 或 WebP 圖片。");
        }

        await using var buffer = new MemoryStream();
        await cover.CopyToAsync(buffer, cancellationToken);
        var content = buffer.ToArray();

        if (!MatchesImageSignature(content, contentType))
        {
            return CoverUploadResult.Invalid("封面圖片內容無法辨識，請重新選擇 JPG、PNG、GIF 或 WebP 圖片。");
        }

        return new CoverUploadResult(content, contentType, null);
    }

    static bool MatchesImageSignature(byte[] content, string contentType) => contentType switch
    {
        "image/jpeg" => content.Length >= 3 && content[0] == 0xFF && content[1] == 0xD8 && content[2] == 0xFF,
        "image/png" => content.AsSpan().StartsWith(new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A }),
        "image/gif" => content.AsSpan().StartsWith("GIF87a"u8) || content.AsSpan().StartsWith("GIF89a"u8),
        "image/webp" => content.Length >= 12
            && content.AsSpan(0, 4).SequenceEqual("RIFF"u8)
            && content.AsSpan(8, 4).SequenceEqual("WEBP"u8),
        _ => false,
    };

    static bool IsSupportedCoverType(string contentType) => contentType is
        "image/jpeg" or "image/png" or "image/gif" or "image/webp";

    sealed record CoverUploadResult(byte[]? Content, string? ContentType, string? Error)
    {
        public static CoverUploadResult Invalid(string error) => new(null, null, error);
    }


}
