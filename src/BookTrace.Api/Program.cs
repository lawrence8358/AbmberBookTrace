using BookTrace.Api.Services;
using BookTrace.Mcp;
using BookTrace.Api.Contracts;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using BookTrace.Api.Storage;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.FileProviders;

var builder = WebApplication.CreateBuilder(args);
var mcpEnabled = builder.Configuration.GetValue("Mcp:Enabled", true);
if (mcpEnabled)
{
    builder.Services.AddScoped<IBookCatalog, McpBookCatalog>();
    builder.Services.AddBookTraceMcp();
}

var connectionString = builder.Configuration.GetConnectionString("BookTrace")
    ?? "Data Source=booktrace.db";
builder.Services.AddDbContext<BookDbContext>(options => options.UseSqlite(connectionString));
builder.Services.AddHostedService<RecycleBinCleanupService>();
builder.Services.AddSingleton<CoverStorage>();
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
        await database.Database.EnsureDeletedAsync();
    }
    await database.Database.MigrateAsync();
    await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(
        database,
        scope.ServiceProvider.GetRequiredService<CoverStorage>(),
        scope.ServiceProvider.GetRequiredService<TimeProvider>(),
        CancellationToken.None);
}

app.Use(async (context, next) =>
{
    if (context.Request.Path.StartsWithSegments("/api") || context.Request.Path.StartsWithSegments("/mcp"))
    {
        var database = context.RequestServices.GetRequiredService<BookDbContext>();
        var timeProvider = context.RequestServices.GetRequiredService<TimeProvider>();
        await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(database, context.RequestServices.GetRequiredService<CoverStorage>(), timeProvider, context.RequestAborted);
    }

    await next(context);
});

app.UseDefaultFiles();
app.UseStaticFiles();
app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(app.Services.GetRequiredService<CoverStorage>().RootPath),
    RequestPath = "/covers",
    OnPrepareResponse = context =>
    {
        context.Context.Response.Headers.CacheControl = "public,max-age=31536000,immutable";
        context.Context.Response.Headers.XContentTypeOptions = "nosniff";
    },
});

app.MapGet("/health", () => Results.Ok(new { status = "ok", mcpEnabled }));
if (mcpEnabled) app.MapBookTraceMcp();
else app.Map("/mcp", () => Results.NotFound());

app.MapGet("/api/books", BookOperations.ListAsync);

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

app.MapGet("/api/books/{id:int}", BookOperations.GetAsync);

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
    var today = DateOnly.FromDateTime(timeProvider.GetLocalNow().DateTime);
    var tomorrowUtc = today.AddDays(1).ToDateTime(TimeOnly.MinValue, DateTimeKind.Utc);
    var records = await database.BorrowingRecords
        .AsNoTracking()
        .Include(record => record.Book)
        .Where(record => record.ReturnedAtUtc == null
            && !record.Book.IsDeleted
            && record.DueDateUtc != null
            && record.DueDateUtc < tomorrowUtc)
        .OrderBy(record => record.DueDateUtc)
        .ThenBy(record => record.BorrowDateUtc)
        .ToListAsync(cancellationToken);

    return Results.Ok(records
        .Where(record => DateOnly.FromDateTime(record.DueDateUtc!.Value) <= today)
        .Select(record => BorrowingReminderResponse.From(record, today))
        .ToList());
});

app.MapPost("/api/books", BookOperations.CreateAsync);

app.MapPut("/api/books/{id:int}", BookOperations.UpdateAsync);

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
    CoverStorage storage,
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
    if (book.DeletedAtUtc.Value < now.AddDays(-30))
    {
        await database.BorrowingRecords
            .Where(record => record.BookId == book.Id)
            .ExecuteDeleteAsync(cancellationToken);
        database.Books.Remove(book);
        await database.SaveChangesAsync(cancellationToken);
        storage.Delete(book.CoverStorageName);
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
    var localBorrowDate = DateOnly.FromDateTime(timeProvider.GetLocalNow().DateTime);
    DateTime? dueDateUtc = request.ClearDueDate
        ? (DateTime?)null
        : request.DueDate is null
            ? localBorrowDate.AddDays(14).ToDateTime(TimeOnly.MinValue, DateTimeKind.Utc)
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

app.MapPost("/api/books/{id:int}/cover", BookOperations.UploadCoverAsync).DisableAntiforgery();

app.MapDelete("/api/books/{id:int}/cover", async (
    int id,
    BookDbContext database,
    CoverStorage storage,
    TimeProvider timeProvider,
    CancellationToken cancellationToken) =>
{
    var book = await database.Books
        .SingleOrDefaultAsync(candidate => candidate.Id == id && !candidate.IsDeleted, cancellationToken);
    if (book is null)
    {
        return Results.NotFound(new { message = "找不到這本書。" });
    }

    if (book.CoverStorageName is null)
    {
        return Results.NotFound(new { message = "這本書目前沒有封面。" });
    }

    var oldName = book.CoverStorageName;
    book.CoverStorageName = null;
    book.CoverContentType = null;
    book.CoverFileName = null;
    book.UpdatedAtUtc = timeProvider.GetUtcNow().UtcDateTime;
    await database.SaveChangesAsync(cancellationToken);
    storage.Delete(oldName);

    return Results.NoContent();
});

app.MapFallbackToFile("index.html");

app.Run();

static string? TrimToNull(string? value) =>
    string.IsNullOrWhiteSpace(value) ? null : value.Trim();

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
            await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(database, scope.ServiceProvider.GetRequiredService<CoverStorage>(), timeProvider, cancellationToken);
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
        CoverStorage storage,
        TimeProvider timeProvider,
        CancellationToken cancellationToken)
    {
        var expirationCutoff = timeProvider.GetUtcNow().UtcDateTime.AddDays(-30);
        var expiredBooks = await database.Books
            .Include(book => book.BorrowingRecords)
            .Where(book => book.IsDeleted
                && book.DeletedAtUtc != null
                && book.DeletedAtUtc < expirationCutoff)
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
        foreach (var book in expiredBooks) storage.Delete(book.CoverStorageName);
    }
}
