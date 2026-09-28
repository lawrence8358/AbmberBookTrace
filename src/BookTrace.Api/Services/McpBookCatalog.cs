using System.Text.Json;
using System.Text.Json.Nodes;
using BookTrace.Api.Contracts;
using BookTrace.Api.Data;
using BookTrace.Api.Storage;
using BookTrace.Mcp;
using ModelContextProtocol;

namespace BookTrace.Api.Services;

public sealed class McpBookCatalog(BookDbContext database, CoverStorage storage, TimeProvider timeProvider) : IBookCatalog
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    public async Task<JsonElement> ListAsync(string? search, string? status, CancellationToken cancellationToken) =>
        Read(await BookOperations.ListAsync(search, status, database, cancellationToken));

    public async Task<JsonElement> GetAsync(int id, CancellationToken cancellationToken) =>
        Read(await BookOperations.GetAsync(id, database, cancellationToken));

    public async Task<JsonElement> SaveAsync(int? id, JsonElement fields, bool fillMissingOnly, CancellationToken cancellationToken)
    {
        try
        {
            if (id is null)
            {
                var request = fields.Deserialize<CreateBookRequest>(JsonOptions)! with { SkipIfExists = true };
                var result = await BookOperations.CreateAsync(request, database, timeProvider, cancellationToken);
                var book = Read(result);
                return JsonSerializer.SerializeToElement(new { created = ((IStatusCodeHttpResult)result).StatusCode == 201, book }, JsonOptions);
            }

            // Keep the read/merge/write atomic so enrichment cannot overwrite a concurrent edit.
            await using var transaction = await database.Database.BeginTransactionAsync(cancellationToken);
            var existing = JsonNode.Parse((await GetAsync(id.Value, cancellationToken)).GetRawText())!.AsObject();
            foreach (var field in fields.EnumerateObject())
            {
                if (field.Value.ValueKind == JsonValueKind.Null) continue;
                var current = existing[field.Name];
                if (fillMissingOnly && current is not null && !string.IsNullOrWhiteSpace(current.ToString())) continue;
                existing[field.Name] = JsonNode.Parse(field.Value.GetRawText());
            }
            var update = existing.Deserialize<UpdateBookRequest>(JsonOptions)!;
            var updated = Read(await BookOperations.UpdateAsync(id.Value, update, database, timeProvider, cancellationToken));
            await transaction.CommitAsync(cancellationToken);
            return updated;
        }
        catch (JsonException)
        {
            throw new McpException("日期請使用有效的 YYYY-MM-DD，未知日期請留空。");
        }
    }

    public async Task<JsonElement> UploadCoverAsync(int id, byte[] content, string contentType, CancellationToken cancellationToken)
    {
        using var stream = new MemoryStream(content);
        var file = new FormFile(stream, 0, content.Length, "cover", "mcp-cover")
        {
            Headers = new HeaderDictionary(), ContentType = contentType,
        };
        return Read(await BookOperations.UploadCoverAsync(id, file, database, storage, timeProvider, cancellationToken));
    }

    private static JsonElement Read(IResult result)
    {
        var value = JsonSerializer.SerializeToElement(((IValueHttpResult)result).Value, JsonOptions);
        if (((IStatusCodeHttpResult)result).StatusCode >= 400)
            throw new McpException(value.GetProperty("message").GetString()!);
        return value;
    }
}
