using System.ComponentModel;
using System.Text.Json;
using ModelContextProtocol;
using ModelContextProtocol.Server;

namespace BookTrace.Mcp;

[McpServerToolType]
public sealed class BookTools(IBookCatalog catalog)
{
    [McpServerTool(Name = "list_books", ReadOnly = true), Description("列出書架藏書，排除回收筒。search 搜尋書名、作者、ISBN；status 為 ALL、HOME 或 BORROWED。")]
    public Task<JsonElement> ListBooks(string? search = null, string status = "ALL", CancellationToken cancellationToken = default) =>
        catalog.ListAsync(search, status, cancellationToken);

    [McpServerTool(Name = "find_book", ReadOnly = true), Description("以 ISBN（忽略空白、連字號）或完整書名及選填作者比對書架，回傳 exists 和所有符合的 books。先核對版本再新增或更新。")]
    public async Task<object> FindBook(string? isbn = null, string? title = null, string? author = null, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(isbn) && string.IsNullOrWhiteSpace(title)) throw new McpException("請提供 ISBN 或書名。");
        var books = await catalog.ListAsync(null, null, cancellationToken);
        var matches = books.EnumerateArray().Where(book =>
            (!string.IsNullOrWhiteSpace(isbn) && NormalizeIsbn(book.GetProperty("isbn").GetString()) == NormalizeIsbn(isbn))
            || (!string.IsNullOrWhiteSpace(title)
                && string.Equals(book.GetProperty("title").GetString()?.Trim(), title.Trim(), StringComparison.OrdinalIgnoreCase)
                && (string.IsNullOrWhiteSpace(author) || string.Equals(book.GetProperty("author").GetString()?.Trim(), author.Trim(), StringComparison.OrdinalIgnoreCase))))
            .ToArray();
        return new { exists = matches.Length > 0, books = matches };
    }

    [McpServerTool(Name = "get_book", ReadOnly = true), Description("依 ID 讀取完整書籍資訊，包括 publicationDate 出版日期、purchaseDate 購入日期、封面網址和借閱狀態。")]
    public Task<JsonElement> GetBook(int id, CancellationToken cancellationToken = default) => catalog.GetAsync(id, cancellationToken);

    [McpServerTool(Name = "add_book", Destructive = false), Description("新增藏書，書名必填；相同 ISBN 或書名／作者已存在時回傳 created=false 與既有書籍。日期使用 YYYY-MM-DD，未知留空。新增後使用 upload_book_cover 上傳實際封面。")]
    public Task<JsonElement> AddBook(string title, string? author = null, string? isbn = null,
        string? publisher = null, string? category = null, string? location = null,
        string? detailedLocation = null, string? notes = null,
        [Description("出版日期 YYYY-MM-DD；未知留空")] string? publicationDate = null,
        [Description("使用者提供的購入日期 YYYY-MM-DD；未知留空")] string? purchaseDate = null,
        CancellationToken cancellationToken = default) =>
        catalog.SaveAsync(null, Fields(title, author, isbn, publisher, category, location, detailedLocation, notes, publicationDate, purchaseDate), false, cancellationToken);

    [McpServerTool(Name = "update_book", Destructive = false), Description("更新既有書籍。預設 fillMissingOnly=true 只補空欄，保留使用者原有資料；明確要修改已有值時設 false。省略或 null 的欄位保留原值。日期 YYYY-MM-DD。")]
    public Task<JsonElement> UpdateBook(int id, string? title = null, string? author = null, string? isbn = null,
        string? publisher = null, string? category = null, string? location = null,
        string? detailedLocation = null, string? notes = null, string? publicationDate = null,
        string? purchaseDate = null, bool fillMissingOnly = true, CancellationToken cancellationToken = default) =>
        catalog.SaveAsync(id, Fields(title, author, isbn, publisher, category, location, detailedLocation, notes, publicationDate, purchaseDate), fillMissingOnly, cancellationToken);

    [McpServerTool(Name = "upload_book_cover", Destructive = false), Description("上傳或替換書籍封面。imageBase64 為圖片原始位元組的 Base64（不含 data: 前綴），contentType 為 image/jpeg、image/png、image/gif 或 image/webp；圖片最大 5 MB。回傳書籍與可讀取的 coverUrl。")]
    public Task<JsonElement> UploadBookCover(int id, string imageBase64, string contentType, CancellationToken cancellationToken = default)
    {
        if (imageBase64.Length > 4 * ((5 * 1024 * 1024 + 2) / 3)) throw new McpException("封面圖片不可超過 5 MB。");
        byte[] content;
        try { content = Convert.FromBase64String(imageBase64); }
        catch (FormatException) { throw new McpException("封面必須是有效的 Base64 圖片內容。"); }
        return catalog.UploadCoverAsync(id, content, contentType, cancellationToken);
    }

    private static JsonElement Fields(string? title, string? author, string? isbn, string? publisher,
        string? category, string? location, string? detailedLocation, string? notes, string? publicationDate, string? purchaseDate) =>
        JsonSerializer.SerializeToElement(new { title, author, isbn, publisher, category, location, detailedLocation, notes, publicationDate, purchaseDate });

    private static string NormalizeIsbn(string? value) =>
        new string((value ?? "").Where(character => !char.IsWhiteSpace(character) && character != '-').ToArray()).ToUpperInvariant();
}
