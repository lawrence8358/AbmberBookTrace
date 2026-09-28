using System.Text.Json;

namespace BookTrace.Mcp;

public interface IBookCatalog
{
    Task<JsonElement> ListAsync(string? search, string? status, CancellationToken cancellationToken);
    Task<JsonElement> GetAsync(int id, CancellationToken cancellationToken);
    Task<JsonElement> SaveAsync(int? id, JsonElement fields, bool fillMissingOnly, CancellationToken cancellationToken);
    Task<JsonElement> UploadCoverAsync(int id, byte[] content, string contentType, CancellationToken cancellationToken);
}
