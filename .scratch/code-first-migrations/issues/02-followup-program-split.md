# 02: 拆分 Program.cs（後續，不在這次範圍）

**What to build:** `src/BookTrace.Api/Program.cs` 目前有 777 行，把 DI 設定、啟動流程、全部 API 端點、封面圖片處理、回收桶維護、背景服務都寫在同一個檔案裡。這張單記錄這個問題，等 01 完成後再決定要不要處理。

**Blocked by:** 01-adopt-ef-migrations

**Status:** backlog

**Labels:** needs-triage

## 可能的切法

- `Endpoints/`：依資源分成 `BookEndpoints`、`BorrowingEndpoints`、`RecycleBinEndpoints` 等，各自用擴充方法註冊。
- `Services/`：`RecycleBinCleanupService`、`RecycleBinMaintenance`、`FixedTimeProvider` 移出來。
- `Program.cs` 只留下組裝：讀設定、註冊服務、掛端點、啟動。

## Comments

- 這是使用者在討論 migration 時順帶提到「資料夾架構全部都寫在一起有點亂」而記下的，還沒確認要做。
