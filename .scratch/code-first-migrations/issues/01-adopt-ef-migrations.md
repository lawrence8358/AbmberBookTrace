# 01: 改用 EF Core Migrations 建立資料表

**What to build:** 讓資料表完全由模型產生，啟動時自動套用，並移除所有手寫 SQL。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Labels:** ready-for-agent

## 做法

1. **加入設計時套件。** 在 `src/BookTrace.Api/BookTrace.Api.csproj` 加 `Microsoft.EntityFrameworkCore.Design`，版本對齊現有的 `Microsoft.EntityFrameworkCore.Sqlite` 10.0.12。這個套件只有產生 migration 時需要，會自動標記為不隨程式發布。

2. **產生第一份 migration，放進獨立資料夾。**

   ```
   dotnet ef migrations add InitialCreate \
     --project src/BookTrace.Api \
     --output-dir Data/Migrations
   ```

   `--output-dir` 讓 migration 檔案集中在 `src/BookTrace.Api/Data/Migrations/`，跟 `BookDbContext.cs` 分開。這個資料夾之後只會放 migration，不放別的程式碼。

3. **確認產生的 migration 涵蓋完整模型。** 對照現在手寫 SQL 補的欄位，確認 `Books` 有 `CoverImageData`、`CoverContentType`、`CoverFileName`、`IsDeleted`、`DeletedAtUtc`，`BorrowingRecords` 整張表與 `IX_BorrowingRecords_BookId` 索引都在。這些欄位在 `Book.cs` / `BorrowingRecord.cs` 裡都已經有，所以應該會自動出現；若缺少表示模型本身漏了，要先補模型而不是補 SQL。

4. **改寫啟動流程。** `src/BookTrace.Api/Program.cs` 的啟動區塊改成：

   ```csharp
   using (var scope = app.Services.CreateScope())
   {
       var database = scope.ServiceProvider.GetRequiredService<BookDbContext>();
       if (app.Environment.IsEnvironment("Playwright"))
       {
           database.Database.EnsureDeleted();
       }
       await database.Database.MigrateAsync();
       await RecycleBinMaintenance.PurgeExpiredDeletedBooksAsync(...);
   }
   ```

   也就是把 `EnsureCreated()`、`EnsureBookColumns(database)`、`SqliteSchemaUpgrade.EnsureBorrowingRecordSchema(database)` 三行換成一行 `MigrateAsync()`。Playwright 環境的 `EnsureDeleted()` 保留，測試前清空資料庫的行為不變。

5. **刪掉手寫 SQL。** 刪除整個 `src/BookTrace.Api/Data/SqliteSchemaUpgrade.cs`，以及 `Program.cs` 裡的 `EnsureBookColumns` 方法（約 599-651 行）。順便檢查 `using System.Data;` 是否還有人用，沒有就一併移除。

## 驗收

- [x] `grep -rn "PRAGMA\|ALTER TABLE\|CREATE TABLE" src/BookTrace.Api --include=*.cs` 只在 `Data/Migrations/` 底下有結果（migration 自己產生的 SQL 是預期的）。
- [x] `src/BookTrace.Api/Data/SqliteSchemaUpgrade.cs` 已刪除。
- [x] `dotnet build src/BookTrace.Api` 通過。
- [x] 刪掉 `booktrace.db` 後啟動，資料表正常建立，`/health` 回應正常。
- [x] `pnpm build && pnpm test:e2e` 全部通過。
- [x] 臨時在 `Book` 上加一個測試欄位、跑 `dotnet ef migrations add`、重啟後確認欄位出現在資料庫，驗證完把測試欄位和該 migration 移除。

## Comments
- 2026-09-22：完成實作。加入 `Microsoft.EntityFrameworkCore.Design`（`PrivateAssets=all`，不隨發布輸出），產生 `Data/Migrations/20260922014405_InitialCreate`，啟動改為 `await database.Database.MigrateAsync()`，刪除 `SqliteSchemaUpgrade.cs` 與 `EnsureBookColumns`，並移除不再使用的 `using System.Data;`。
- 2026-09-22：驗證 auto migration 確實生效——臨時在 `Book` 加 `MigrationProbe` 欄位、產生第二份 migration、重啟後確認欄位出現在資料庫且既有資料列保留，接著把測試欄位與該 migration 移除。
- 2026-09-22：Playwright 20 個測試全部通過（本機以覆寫設定指向 Windows 的 Chrome 執行，該覆寫檔驗證後已刪除；`playwright.config.ts` 未變動）。
- 2026-09-22：code review 後續處理。把 `EnsureDeleted()` 改成 `await EnsureDeletedAsync()`，與旁邊的非同步呼叫一致；`02` 的標籤從自創的 `needs-decision` 改成 `docs/agents/triage-labels.md` 列的 `needs-triage`。另外實際跑 `dotnet publish` 確認 `Microsoft.EntityFrameworkCore.Design.dll` 不在輸出裡（該套件的 nuspec 標記為 development dependency），所以發布成品不受影響。
