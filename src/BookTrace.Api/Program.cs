using BookTrace.Api.Contracts;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using Microsoft.EntityFrameworkCore;
using System.Data;

const long MaxCoverSizeBytes = 5 * 1024 * 1024;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("BookTrace")
    ?? "Data Source=booktrace.db";
builder.Services.AddDbContext<BookDbContext>(options => options.UseSqlite(connectionString));
builder.Services.AddHostedService<RecycleBinCleanupService>();
builder.Services.AddSingleton<TimeProvider>(_ =>
{
    var configuredNow = Environment.GetEnvironmentVariable("BOOKTRACE_NOW_UTC");
    if (builder.Environment.IsEnvironment("Playwright")
        && DateTimeOffset.TryParse(configuredNow, out var fixedNow))
    {
        return new FixedTimeProvider(fixedNow.ToUniversalTime());
    }

    return TimeProvider.System;
});

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var database = scope.ServiceProvider.GetRequiredService<BookDbContext>();
    if (app.Environment.IsEnvironment("Playwright"))
    {
        database.Database.EnsureDeleted();
    }
    database.Database.EnsureCreated();
    EnsureBookColumns(database);
    await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(
        database,
        scope.ServiceProvider.GetRequiredService<TimeProvider>(),
        CancellationToken.None);
}

app.Use(async (context, next) =>
{
    if (context.Request.Path.StartsWithSegments("/api"))
    {
        var database = context.RequestServices.GetRequiredService<BookDbContext>();
        var timeProvider = context.RequestServices.GetRequiredService<TimeProvider>();
        await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(database, timeProvider, context.RequestAborted);
    }

    await next(context);
});

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapGet("/api/books", async (
    string? search,
    string? status,
    BookDbContext database,
    CancellationToken cancellationToken) =>
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
});

app.MapGet("/api/books/stats", async (
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var books = database.Books
        .AsNoTracking()
        .Where(book => !book.IsDeleted);
    var totalCount = await books.CountAsync(cancellationToken);
    var homeCount = await books.CountAsync(book => book.Status == BookStatus.Home, cancellationToken);
    var borrowedCount = await books.CountAsync(book => book.Status == BookStatus.Borrowed, cancellationToken);
    var recentBooks = await books
        .OrderByDescending(book => book.CreatedAtUtc)
        .ThenByDescending(book => book.Id)
        .Take(4)
        .Select(book => BookResponse.From(book))
        .ToListAsync(cancellationToken);

    return Results.Ok(new LibraryStatsResponse(totalCount, homeCount, borrowedCount, recentBooks));
});

app.MapGet("/api/books/{id:int}", async (
    int id,
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .AsNoTracking()
        .Include(candidate => candidate.BorrowingRecords
            .Where(record => record.ReturnedAtUtc == null))
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);

    return book is null
        ? Results.NotFound(new { message = "找不到這本書。" })
        : Results.Ok(BookResponse.From(book, book.BorrowingRecords.SingleOrDefault()));
});

app.MapGet("/api/books/{id:int}/borrowing-history", async (
    int id,
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var bookExists = await database.Books
        .AsNoTracking()
        .AnyAsync(book => book.Id == id && !book.IsDeleted, cancellationToken);
    if (!bookExists)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    var history = await database.BorrowingRecords
        .AsNoTracking()
        .Include(record => record.Book)
        .Where(record => record.BookId == id)
        .OrderByDescending(record => record.BorrowDateUtc)
        .ThenByDescending(record => record.Id)
        .ToListAsync(cancellationToken);

    return Results.Ok(history.Select(BorrowingHistoryResponse.From).ToList());
});

app.MapGet("/api/borrowings", async (
    string? status,
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var historyQuery = database.BorrowingRecords
        .AsNoTracking()
        .Include(record => record.Book)
        .AsQueryable();

    if (!string.IsNullOrWhiteSpace(status)
        && !status.Equals("ALL", StringComparison.OrdinalIgnoreCase))
    {
        if (status.Equals("CURRENT", StringComparison.OrdinalIgnoreCase))
        {
            historyQuery = historyQuery.Where(record => record.ReturnedAtUtc == null);
        }
        else if (status.Equals("RETURNED", StringComparison.OrdinalIgnoreCase))
        {
            historyQuery = historyQuery.Where(record => record.ReturnedAtUtc != null);
        }
        else
        {
            return Results.BadRequest(new { message = "無法辨識這個借閱歷史篩選。" });
        }
    }

    var history = await historyQuery
        .OrderBy(record => record.ReturnedAtUtc != null)
        .ThenByDescending(record => record.BorrowDateUtc)
        .ThenByDescending(record => record.Id)
        .ToListAsync(cancellationToken);

    return Results.Ok(history.Select(BorrowingHistoryResponse.From).ToList());
});

app.MapGet("/api/reminders", async (
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var today = DateOnly.FromDateTime(timeProvider.GetUtcNow().UtcDateTime);
    var tomorrow = today.ToDateTime(TimeOnly.MinValue, DateTimeKind.Utc).AddDays(1);
    var records = await database.BorrowingRecords
        .AsNoTracking()
        .Include(record => record.Book)
        .Where(record => record.ReturnedAtUtc == null
            && !record.Book.IsDeleted
            && record.DueDateUtc != null
            && record.DueDateUtc < tomorrow)
        .OrderBy(record => record.DueDateUtc)
        .ThenBy(record => record.BorrowDateUtc)
        .ToListAsync(cancellationToken);

    return Results.Ok(records
        .Where(record => DateOnly.FromDateTime(record.DueDateUtc!.Value) <= today)
        .Select(record => BorrowingReminderResponse.From(record, today))
        .ToList());
});

app.MapGet("/api/books/{id:int}/cover", async (
    int id,
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var cover = await database.Books
        .AsNoTracking()
        .Where(book => book.Id == id)
        .Select(book => new { book.CoverImageData, book.CoverContentType })
        .SingleOrDefaultAsync(cancellationToken);

    return cover?.CoverImageData is null || cover.CoverContentType is null
        ? Results.NotFound()
        : Results.File(cover.CoverImageData, cover.CoverContentType);
});

app.MapPost("/api/books", async (
    CreateBookRequest request,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    if (string.IsNullOrWhiteSpace(request.Title))
    {
        return Results.BadRequest(new
        {
            message = "請輸入書名，才能保存這本書。",
            errors = new { title = "書名是必填欄位。" },
        });
    }

    var now = timeProvider.GetUtcNow().UtcDateTime;
    var book = new Book
    {
        Title = request.Title.Trim(),
        Author = TrimToNull(request.Author),
        Isbn = TrimToNull(request.Isbn),
        Publisher = TrimToNull(request.Publisher),
        Category = TrimToNull(request.Category),
        Location = TrimToNull(request.Location),
        DetailedLocation = TrimToNull(request.DetailedLocation),
        Notes = TrimToNull(request.Notes),
        Status = BookStatus.Home,
        CreatedAtUtc = now,
        UpdatedAtUtc = now,
    };

    database.Books.Add(book);
    await database.SaveChangesAsync(cancellationToken);

    return Results.Created($"/api/books/{book.Id}", BookResponse.From(book));
});

app.MapPut("/api/books/{id:int}", async (
    int id,
    UpdateBookRequest request,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
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

    book.Title = request.Title.Trim();
    book.Author = TrimToNull(request.Author);
    book.Isbn = TrimToNull(request.Isbn);
    book.Publisher = TrimToNull(request.Publisher);
    book.Category = TrimToNull(request.Category);
    book.Location = TrimToNull(request.Location);
    book.DetailedLocation = TrimToNull(request.DetailedLocation);
    book.Notes = TrimToNull(request.Notes);
    book.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;

    await database.SaveChangesAsync(cancellationToken);

    return Results.Ok(BookResponse.From(
        book,
        book.BorrowingRecords.SingleOrDefault(record => record.ReturnedAtUtc == null)));
});

app.MapDelete("/api/books/{id:int}", async (
    int id,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .Include(candidate => candidate.BorrowingRecords)
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
    if (book is null)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    var deletedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
    book.IsDeleted = true;
    book.DeletedAtUtc = deletedAtUtc;
    book.UpdatedAtUtc = deletedAtUtc;
    await database.SaveChangesAsync(cancellationToken);

    return Results.Ok(RecycleBinBookResponse.From(
        book,
        book.BorrowingRecords.SingleOrDefault(record => record.ReturnedAtUtc == null)));
});

app.MapGet("/api/recycle-bin", async (
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var books = await database.Books
        .AsNoTracking()
        .Include(book => book.BorrowingRecords)
        .Where(book => book.IsDeleted)
        .OrderByDescending(book => book.DeletedAtUtc)
        .ThenByDescending(book => book.Id)
        .ToListAsync(cancellationToken);

    return Results.Ok(books.Select(book => RecycleBinBookResponse.From(
        book,
        book.BorrowingRecords.SingleOrDefault(record => record.ReturnedAtUtc == null))));
});

app.MapPost("/api/recycle-bin/{id:int}/restore", async (
    int id,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .Include(candidate => candidate.BorrowingRecords)
        .SingleOrDefaultAsync(candidate => candidate.Id == id && candidate.IsDeleted, cancellationToken);
    if (book is null || book.DeletedAtUtc is null)
    {
        return Results.NotFound(new { message = "回收筒裡找不到這本書，或它已經永久移除。" });
    }

    var now = timeProvider.GetUtcNow().UtcDateTime;
    if (book.DeletedAtUtc.Value <= now.AddDays(-30))
    {
        await database.BorrowingRecords
            .Where(record => record.BookId == book.Id)
            .ExecuteDeleteAsync(cancellationToken);
        database.Books.Remove(book);
        await database.SaveChangesAsync(cancellationToken);
        return Results.NotFound(new { message = "這本書已超過 30 天，無法還原。" });
    }

    book.IsDeleted = false;
    book.DeletedAtUtc = null;
    book.UpdatedAtUtc = now;
    await database.SaveChangesAsync(cancellationToken);

    return Results.Ok(BookResponse.From(
        book,
        book.BorrowingRecords.SingleOrDefault(record => record.ReturnedAtUtc == null)));
});

if (app.Environment.IsEnvironment("Playwright"))
{
    app.MapPost("/api/test/recycle-bin/{id:int}/age", async (
        int id,
        AgeRecycleBinRequest request,
        BookDbContext database,
        TimeProvider timeProvider,
        CancellationToken cancellationToken) =>
    {
        var book = await database.Books
            .SingleOrDefaultAsync(candidate => candidate.Id == id && candidate.IsDeleted, cancellationToken);
        if (book is null)
        {
            return Results.NotFound(new { message = "找不到這本回收中的書籍。" });
        }

        var daysAgo = Math.Max(30, request.DaysAgo);
        book.DeletedAtUtc = timeProvider.GetUtcNow().UtcDateTime.AddDays(-daysAgo);
        await database.SaveChangesAsync(cancellationToken);
        return Results.NoContent();
    });
}

app.MapPost("/api/books/{id:int}/borrow", async (
    int id,
    BorrowBookRequest request,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .Include(candidate => candidate.BorrowingRecords)
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);

    if (book is null)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    if (book.Status != BookStatus.Home || book.BorrowingRecords.Any(record => record.ReturnedAtUtc == null))
    {
        return Results.Conflict(new { message = "這本書目前已經借出中，無法重複借出。" });
    }

    if (string.IsNullOrWhiteSpace(request.BorrowerName))
    {
        return Results.BadRequest(new
        {
            message = "請輸入借閱人，才能完成借出。",
            errors = new { borrowerName = "借閱人是必填欄位。" },
        });
    }

    var borrowDateUtc = timeProvider.GetUtcNow().UtcDateTime;
    DateTime? dueDateUtc = request.ClearDueDate
        ? (DateTime?)null
        : request.DueDate is null
            ? DateTime.SpecifyKind(borrowDateUtc.Date.AddDays(14), DateTimeKind.Utc)
            : request.DueDate.Value.ToDateTime(TimeOnly.MinValue, DateTimeKind.Utc);
    var record = new BorrowingRecord
    {
        BookId = book.Id,
        BorrowerName = request.BorrowerName.Trim(),
        BorrowDateUtc = borrowDateUtc,
        DueDateUtc = dueDateUtc,
        Note = TrimToNull(request.Note),
    };

    book.Status = BookStatus.Borrowed;
    book.UpdatedAtUtc = borrowDateUtc;
    book.BorrowingRecords.Add(record);

    await database.SaveChangesAsync(cancellationToken);

    return Results.Ok(BookResponse.From(book, record));
});

app.MapPost("/api/books/{id:int}/return", async (
    int id,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .Include(candidate => candidate.BorrowingRecords)
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
    if (book is null)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    var currentBorrowing = book.BorrowingRecords
        .SingleOrDefault(record => record.ReturnedAtUtc == null);
    if (book.Status != BookStatus.Borrowed || currentBorrowing is null)
    {
        return Results.Conflict(new { message = "只有借出中的書籍可以歸還。" });
    }

    var returnedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
    currentBorrowing.ReturnedAtUtc = returnedAtUtc;
    book.Status = BookStatus.Home;
    book.UpdatedAtUtc = returnedAtUtc;

    await database.SaveChangesAsync(cancellationToken);

    return Results.Ok(BookResponse.From(book));
});

app.MapPost("/api/books/{id:int}/cover", async (
    int id,
    IFormFile? cover,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
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
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
    if (book is null)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    book.CoverImageData = upload.Content;
    book.CoverContentType = upload.ContentType;
    book.CoverFileName = Path.GetFileName(cover.FileName);
    book.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
    await database.SaveChangesAsync(cancellationToken);

    return Results.Ok(BookResponse.From(book));
}).DisableAntiforgery();

app.MapDelete("/api/books/{id:int}/cover", async (
    int id,
    BookDbContext database,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
    if (book is null)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    if (book.CoverImageData is null)
    {
        return Results.NotFound(new { message = "這本書目前沒有封面。" });
    }

    book.CoverImageData = null;
    book.CoverContentType = null;
    book.CoverFileName = null;
    book.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
    await database.SaveChangesAsync(cancellationToken);

    return Results.NoContent();
});

app.MapFallbackToFile("index.html");

app.Run();

static string? TrimToNull(string? value) =>
    string.IsNullOrWhiteSpace(value) ? null : value.Trim();

static void EnsureBookColumns(BookDbContext database)
{
    var connection = database.Database.GetDbConnection();
    var shouldClose = connection.State != ConnectionState.Open;
    if (shouldClose)
    {
        connection.Open();
    }

    try
    {
        using var columnsCommand = connection.CreateCommand();
        columnsCommand.CommandText = "PRAGMA table_info(Books);";
        var existingColumns = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using (var reader = columnsCommand.ExecuteReader())
        {
            while (reader.Read())
            {
                existingColumns.Add(reader.GetString(1));
            }
        }

        var missingColumns = new (string Name, string SqlType)[]
        {
            ("CoverImageData", "BLOB NULL"),
            ("CoverContentType", "TEXT NULL"),
            ("CoverFileName", "TEXT NULL"),
            ("IsDeleted", "INTEGER NOT NULL DEFAULT 0"),
            ("DeletedAtUtc", "TEXT NULL"),
        };

        foreach (var (name, sqlType) in missingColumns)
        {
            if (existingColumns.Contains(name))
            {
                continue;
            }

            using var alterCommand = connection.CreateCommand();
            alterCommand.CommandText = $"ALTER TABLE Books ADD COLUMN {name} {sqlType};";
            alterCommand.ExecuteNonQuery();
        }
    }
    finally
    {
        if (shouldClose)
        {
            connection.Close();
        }
    }
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

sealed record AgeRecycleBinRequest(int DaysAgo);

sealed class RecycleBinCleanupService(
    IServiceScopeFactory scopeFactory,
    TimeProvider timeProvider,
    ILogger<RecycleBinCleanupService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        using var timer = new PeriodicTimer(TimeSpan.FromHours(1));
        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                await CleanupAsync(stoppingToken);
            }
        }
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {
        }
    }

    private async Task CleanupAsync(CancellationToken cancellationToken)
    {
        await using var scope = scopeFactory.CreateAsyncScope();
        var database = scope.ServiceProvider.GetRequiredService<BookDbContext>();
        try
        {
            await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(database, timeProvider, cancellationToken);
        }
        catch (Exception exception) when (exception is not OperationCanceledException)
        {
            logger.LogError(exception, "無法清理超過 30 天的回收筒書籍。");
        }
    }
}

sealed class FixedTimeProvider(DateTimeOffset now) : TimeProvider
{
    private long callCount;

    public override DateTimeOffset GetUtcNow() => now.AddTicks(Interlocked.Increment(ref callCount));
}

public partial class Program;

static class RecycleBinMaintenance
{
    public static async Task PurgeExpiredDeletedBooksAsync(
        BookDbContext database,
        TimeProvider timeProvider,
        CancellationToken cancellationToken)
    {
        var expirationCutoff = timeProvider.GetUtcNow().UtcDateTime.AddDays(-30);
        var expiredBooks = await database.Books
            .Include(book => book.BorrowingRecords)
            .Where(book => book.IsDeleted
                && book.DeletedAtUtc != null
                && book.DeletedAtUtc <= expirationCutoff)
            .ToListAsync(cancellationToken);

        if (expiredBooks.Count == 0)
        {
            return;
        }

        foreach (var book in expiredBooks)
        {
            database.BorrowingRecords.RemoveRange(book.BorrowingRecords);
            database.Books.Remove(book);
        }

        await database.SaveChangesAsync(cancellationToken);
    }
}
