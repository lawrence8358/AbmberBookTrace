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

app.MapGet("/api/books", async (BookDbContext database, CancellationToken cancellationToken) =>
{
    var books = await database.Books
        .AsNoTracking()
        .OrderByDescending(book => book.CreatedAtUtc)
        .Select(book => BookResponse.From(book))
        .ToListAsync(cancellationToken);

    return Results.Ok(books);
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
