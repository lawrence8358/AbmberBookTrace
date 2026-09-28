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

- `1. 開啟 API`：以偵錯器啟動 API（`http://localhost:5000`）。
- `2. 開啟前端`：啟動 Vite 並開啟 Chrome（`http://localhost:5173`）。
- `3. 同時開啟前後端`：同時啟動以上兩個偵錯工作階段。

VS Code 會推薦安裝 C# Dev Kit 與 Vue 擴充套件；第一次使用前仍需先安裝前端依賴。

## 測試

後端整合測試使用獨立暫存資料庫與圖片目錄，包含圖片持久化、靜態快取、HTTP MCP 與重複新增檢查：

```bash
dotnet test BookTrace.sln
```

瀏覽器流程測試會自動建立前端產物，並在 Playwright 環境使用乾淨的 SQLite 資料庫：

```bash
pnpm test:e2e
```

## 封面圖片目錄

API 的 `appsettings.json` 使用 `CoverStorage:Path` 設定圖片目錄，預設為 `uploads/covers`（相對於 API 的內容根目錄），也接受絕對路徑。Docker 可設定環境變數 `CoverStorage__Path=/data/covers` 並將 volume 掛載到 `/data/covers`；資料庫仍須另外掛載保存。

封面由 `/covers/<唯一檔名>` 提供，支援 ETag、Last-Modified 與一年 immutable 快取；換圖會產生新網址。替換、移除封面或回收筒到期後會刪除舊檔，進入回收筒時仍保留圖片供還原。

圖片只使用檔案儲存，不支援舊版 BLOB 圖片或舊的封面讀取網址。資料庫更新會移除 `CoverImageData` 欄位，舊圖片不會自動搬移，需要重新上傳。備份需同時包含資料庫與圖片目錄。

## 書籍日期

新增、修改與詳情頁均支援「出版日期」及「購入日期」。API／MCP 欄位分別為 `publicationDate`、`purchaseDate`，採 `YYYY-MM-DD`，未知可留空；日期不進行時區換算。

## HTTP MCP

`src/BookTrace.Mcp` 是獨立類別庫，由 `BookTrace.Api` 載入，與網站共用程序、連接埠和書籍操作邏輯；不需要額外啟動 MCP 程序。使用官方 [MCP C# SDK 的 Streamable HTTP](https://csharp.sdk.modelcontextprotocol.io/v2/concepts/transports/transports.html)。

API 的 `appsettings.json` 預設開啟 MCP：

```json
{
  "Mcp": {
    "Enabled": true
  }
}
```

依原本方式 `pnpm start` 啟動網站後，本機 LLM 服務連線到 `http://localhost:5000/mcp`；對外站台的 API 基底網址為 `https://booktrace.primeeagle.net/`，MCP 端點為 `https://booktrace.primeeagle.net/mcp`。設定 `Mcp:Enabled=false` 後重啟，可關閉 MCP（回傳 404）。`/health` 包含 `mcpEnabled`。

| 工具 | 用途 |
| --- | --- |
| `list_books` | 列出藏書，可傳 `search`（書名／作者／ISBN）與 `status`（ALL／HOME／BORROWED） |
| `find_book` | 以 `isbn` 或完整 `title`、選填 `author` 確認是否存在，回傳 `exists` 與 `books` |
| `get_book` | 用 `id` 取得完整書籍、日期與借閱狀態 |
| `add_book` | 必填 `title`；可傳作者、ISBN、出版社、分類、位置、備註、`publicationDate`、`purchaseDate` |
| `update_book` | 以 `id` 補齊資料，預設 `fillMissingOnly=true`；設 false 可修改已有值，省略或 null 的欄位保留 |
| `upload_book_cover` | 傳 `id`、`imageBase64`、`contentType`，上傳實際圖片，接受 JPG／PNG／GIF／WebP，最多 5 MB |

`add_book` 在資料庫交易內檢查重複：ISBN 忽略空白與連字號，或書名與作者去除頭尾空白且忽略大小寫；符合時回傳 `created=false` 與既有書籍，不覆寫內容。沒有提供作者時，只與同樣未填作者的書名配對。回收筒內書籍不列入查詢或重複檢查。不同 ISBN 的同名書仍需人工核對版本，不能直接將另一版本的資訊套用到既有書籍。

MCP 支援補齊資料和上傳圖片；照片辨識及網路查書由呼叫端技能執行。回傳的 `coverUrl` 相對於同一站台。Docker 可以用 `Mcp__Enabled=false` 關閉 MCP，圖片掛載方式見上節。目前與原 API 相同未內建登入驗證，遠端部署可由有驗證的反向代理或私人網路提供。

## 外部查書建檔技能範例

供外部代理人安裝使用的技能範例位於 [src/booktrace-enrich-skill/SKILL.md](src/booktrace-enrich-skill/SKILL.md)，可輸入：

> 使用 $booktrace-enrich，幫我把《書名》加入書蹤，包含封面。

也可附上書本照片，請技能辨識後建檔。技能優先查博客來，網站無法讀取時改用出版社或其他書店；核對版本後，透過 MCP 查重、補齊資料並上傳封面。購入日期只使用你提供的日期或收據，不會猜成今天。

隨附 Python 3 腳本只用標準函式庫，支援沒有原生 MCP 連線的環境，且強制要求圖片檔、查證來源和有效日期：

```bash
python src/booktrace-enrich-skill/scripts/enrich_book.py --endpoint https://booktrace.primeeagle.net/mcp --metadata book.json --cover cover.jpg
```

`book.json` 使用上表欄位加上 `sources`（查證網址陣列）；完整流程與格式見技能。預設只補空欄且保留已有封面，要求替換封面時使用 `--replace-cover`。腳本會讀回資料並下載封面驗證；若保存資料後封面上傳失敗，會回報書籍 ID，可用 `--book-id` 重試。

已在隔離書架實測查書、實際封面辨識與上傳、重跑補齊不重複、未知購入日期保留空白、無效圖片拒絕；另有後端整合測試和前端日期／封面流程測試。
