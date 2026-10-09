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

## 登入與權限

網站只有一個登入帳號，帳號與密碼由你自己建立，程式不內建任何預設帳號。

- **第一次使用時自己建立帳號**：資料庫裡還沒有任何帳號時，頭像選單的「登入」會變成「建立帳號」畫面，輸入帳號與密碼（密碼至少 4 個字，不需要大小寫或符號）後會自動登入。建立之後，這個畫面就不能再建立新帳號。**對外站台上線後請立刻自己建立帳號**，否則第一位開啟網站的人就能建立。
- **沒登入只能瀏覽與搜尋**：新增、修改、刪除、借出、歸還、還原書籍與上傳／移除封面都需要登入。畫面會隱藏這些按鈕，**後端也會用 `401` 擋下沒有登入的 API 請求**（讀取類 API 不需要登入）。登入／登出在頭像選單裡。
- **閒置 1 小時自動登出**：1 小時內沒有任何點擊、按鍵或換頁，就會安靜地登出，不會提醒。網站與伺服器都用同一個時限，可用 `Auth:IdleTimeoutMinutes` 調整。
- 連續登入失敗 5 次，會暫停登入 5 分鐘。
- 密碼只保存雜湊值（資料庫的 `Users` 資料表）。**忘記密碼或想換帳號**：從 `Users` 資料表刪除這個帳號，下一次按「登入」又會出現建立帳號畫面。登入後可以在頭像選單選「變更密碼」（新密碼不能和目前的密碼相同）。

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

**MCP 的寫入使用和網站相同的登入**：`add_book`、`update_book`、`upload_book_cover` 會檢查 `Authorization: Basic base64(帳號:密碼)`，帳號與密碼就是網站登入用的那一組，由同一份 `Users` 資料驗證，**伺服器不需要額外設定**；網站還沒有建立帳號時，MCP 也不能寫入。`list_books`、`find_book`、`get_book` 不需要登入。規則和網站一致：

- 在網站變更密碼後，MCP 客戶端也要改用新密碼。
- 密碼錯誤會被拒絕；連續失敗 5 次會暫停 MCP 寫入 5 分鐘（MCP 與網站登入各自計算，不會互相鎖住）。
- 每次寫入都會帶著密碼，請只透過 HTTPS 使用（本機測試網址除外）。

MCP 客戶端需要加上這個 HTTP 標頭。例如 Claude Code（PowerShell）：

```powershell
$auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("帳號:密碼"))
claude mcp add --transport http booktrace https://booktrace.primeeagle.net/mcp --header "Authorization: Basic $auth"
```

其他客戶端請在設定裡加入同樣的 `Authorization` 標頭。小幫手則在設定的「BookTrace 登入」輸入帳號與密碼即可（見 [小幫手說明](src/booktrace-assistant/README.md)）。

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

MCP 支援補齊資料和上傳圖片；照片辨識及網路查書由呼叫端（例如 BookTrace 小幫手）執行。回傳的 `coverUrl` 相對於同一站台。Docker 可以用 `Mcp__Enabled=false` 關閉 MCP，圖片掛載方式見上節。目前與原 API 相同未內建登入驗證，遠端部署可由有驗證的反向代理或私人網路提供。

## BookTrace 小幫手（查書建檔工具）

[src/booktrace-assistant](src/booktrace-assistant/README.md) 是給不熟悉指令列的人使用的本機聊天介面：雙擊啟動後，輸入書名、ISBN 或貼上書本照片，它會呼叫本機的 Claude／Codex CLI 查證版本與封面，經你確認後才透過 MCP 查重、補齊資料並上傳封面。購入日期只使用你提供的日期，不會猜成今天。

隨附的保存工具 `enrich_book.py` 只用 Python 3 標準函式庫，也可單獨執行，強制要求圖片檔、查證來源和有效日期：

```bash
python src/booktrace-assistant/booktrace_assistant/enrich_book.py --endpoint https://booktrace.primeeagle.net/mcp --metadata book.json --cover cover.jpg
```

`book.json` 使用上表欄位加上 `sources`（查證網址陣列）。預設只補空欄且保留已有封面，要求替換封面時使用 `--replace-cover`。腳本會讀回資料並下載封面驗證；若保存資料後封面上傳失敗，會回報書籍 ID，可用 `--book-id` 重試。使用方式、模型與費用設定見 [小幫手說明](src/booktrace-assistant/README.md)。
