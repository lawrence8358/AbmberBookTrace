using BookTrace.Api.Contracts;
using BookTrace.Api.Data;
using BookTrace.Api.Models;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

var connectionString = builder.Configuration.GetConnectionString("BookTrace")
    ?? "Data Source=booktrace.db";
builder.Services.AddDbContext<BookDbContext>(options => options.UseSqlite(connectionString));

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var database = scope.ServiceProvider.GetRequiredService<BookDbContext>();
    if (app.Environment.IsEnvironment("Playwright"))
    {
        database.Database.EnsureDeleted();
    }
    database.Database.EnsureCreated();
}

app.UseDefaultFiles();
app.UseStaticFiles();

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.MapGet("/api/books", async (
    string? search,
    string? status,
    BookDbContext database,
    CancellationToken cancellationToken) =>
{
    var booksQuery = database.Books.AsNoTracking();
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
                : database.Books.Count(candidate => candidate.Author == book.Author),
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
    var books = database.Books.AsNoTracking();
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
        .SingleOrDefaultAsync(candidate => candidate.Id == id, cancellationToken);

    return book is null
        ? Results.NotFound(new { message = "找不到這本書。" })
        : Results.Ok(BookResponse.From(book));
});

app.MapPost("/api/books", async (
    CreateBookRequest request,
    BookDbContext database,
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

    var now = DateTime.UtcNow;
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

app.MapFallbackToFile("index.html");

app.Run();

static string? TrimToNull(string? value) =>
    string.IsNullOrWhiteSpace(value) ? null : value.Trim();

public partial class Program;
