# 規格：改用 EF Core Migrations 的 code first 流程

## 想解決什麼

資料表結構目前不是由模型自動產生，而是靠啟動時跑手寫 SQL 補出來的。這會帶來兩個問題：

1. **綁死 SQLite。** 手寫的 SQL 用了 `PRAGMA table_info`、`AUTOINCREMENT`、`TEXT` 存日期，這些在 SQL Server 或 PostgreSQL 都不能用。將來要轉移資料庫，這些程式碼要整段重寫。
2. **容易漏掉。** 模型加了欄位，必須記得手動再補一段 SQL，忘了就會在執行期才發現資料表少欄位。

## 現況在哪裡

- `src/BookTrace.Api/Data/BookDbContext.cs`：模型定義，這部分已經是正確的 code first。
- `src/BookTrace.Api/Program.cs:36`：`EnsureCreated()`。這個方法只在資料庫不存在時建一次表，之後模型怎麼改它都不管，設計上就不支援結構演進。
- `src/BookTrace.Api/Program.cs:599`：`EnsureBookColumns`，手寫 SQL 補 `Books` 的五個欄位。
- `src/BookTrace.Api/Data/SqliteSchemaUpgrade.cs`：整份手寫 SQL，補 `BorrowingRecords` 這張表和它的欄位、索引。

## 要變成什麼樣

- 資料表結構一律由 EF Core Migrations 從模型產生，程式碼裡不再有任何手寫的建表或改欄位 SQL。
- 應用程式啟動時自動套用尚未執行的 migration（auto migration）。
- Migration 檔案放在自己的資料夾，不跟 `DbContext` 和其他資料存取程式碼混在一起。
- 之後要改結構，流程固定是「改模型 → `dotnet ef migrations add <名稱>` → 啟動自動套用」。

## 前提與範圍

- 使用者已確認：**沒有需要保留的既存資料庫**，可以砍掉重建。所以不需要處理「舊資料庫沒有 `__EFMigrationsHistory`」的相容邏輯。
- 這次只處理資料庫結構的產生方式。`Program.cs` 有 777 行、API 端點全部寫在一起的問題另開一張單，不混在這次改動裡。

## 怎麼算完成

- `src/BookTrace.Api/` 底下找不到任何 `PRAGMA`、`ALTER TABLE`、`CREATE TABLE` 字串。
- 刪掉資料庫檔案後啟動應用程式，資料表由 migration 建立，既有的 Playwright 瀏覽器測試仍然全部通過。
- 在模型上加一個欄位、產生新的 migration、重新啟動後，該欄位確實出現在資料庫裡。
