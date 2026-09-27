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

## VS Code 偵錯

用 VS Code 開啟專案根目錄後，進入「執行與偵錯」並選擇需要的模式，再按 `F5`：

- `1. 開啟 API`：以偵錯器啟動 API（`http://localhost:5080`）。
- `2. 開啟前端`：啟動 Vite 並開啟 Chrome（`http://localhost:5173`）。
- `3. 同時開啟前後端`：同時啟動以上兩個偵錯工作階段。

VS Code 會推薦安裝 C# Dev Kit 與 Vue 擴充套件；第一次使用前仍需先安裝前端依賴。

## 測試

瀏覽器流程測試會自動建立前端產物，並在 Playwright 環境使用乾淨的 SQLite 資料庫：

```bash
pnpm test:e2e
```
