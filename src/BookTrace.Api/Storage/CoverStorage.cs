namespace BookTrace.Api.Storage;

public sealed class CoverStorage
{
    private readonly ILogger<CoverStorage> logger;
    public string RootPath { get; }

    public CoverStorage(IConfiguration configuration, IWebHostEnvironment environment, ILogger<CoverStorage> logger)
    {
        this.logger = logger;
        RootPath = Path.GetFullPath(configuration["CoverStorage:Path"] ?? "uploads/covers", environment.ContentRootPath);
        Directory.CreateDirectory(RootPath);
    }

    public async Task<string> WriteAsync(byte[] content, string contentType, CancellationToken cancellationToken)
    {
        var extension = contentType switch
        {
            "image/jpeg" => ".jpg", "image/png" => ".png",
            "image/gif" => ".gif", "image/webp" => ".webp",
            _ => throw new InvalidOperationException("無法儲存不支援的封面格式。"),
        };
        var name = $"{Guid.NewGuid():N}{extension}";
        var temporaryPath = Path.Combine(RootPath, name + ".tmp");
        try
        {
            await File.WriteAllBytesAsync(temporaryPath, content, cancellationToken);
            File.Move(temporaryPath, Path.Combine(RootPath, name));
            return name;
        }
        finally
        {
            if (File.Exists(temporaryPath)) File.Delete(temporaryPath);
        }
    }

    public void Delete(string? name)
    {
        if (name is null) return;
        if (Path.GetFileName(name) != name) throw new InvalidOperationException("無效的封面檔名。");
        try { File.Delete(Path.Combine(RootPath, name)); }
        catch (Exception exception) when (exception is IOException or UnauthorizedAccessException)
        {
            logger.LogWarning(exception, "無法移除封面檔案 {Name}。", name);
        }
    }

}
