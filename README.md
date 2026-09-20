# 書蹤 BookTrace

「書蹤」是以 Vue 3、ASP.NET Core Web API、SQLite 與 EF Core 建立的個人藏書管理網站。

## 開始使用

先安裝前端依賴，再由根目錄啟動整合後的應用程式：

```bash
pnpm --dir src/booktrace-client install
pnpm start
```

`pnpm start` 會先 typecheck 並建立 Vue 靜態檔，再啟動 ASP.NET Core API 與網站。預設網址是 `http://localhost:5000`；資料會保存到 `src/BookTrace.Api/booktrace.db`。

開發前端畫面時可使用 `pnpm dev`，API 則另開終端機執行 `pnpm dev:api`。

## 測試

瀏覽器流程測試會自動建立前端產物，並在 Playwright 環境使用乾淨的 SQLite 資料庫：

```bash
pnpm test:e2e
```
