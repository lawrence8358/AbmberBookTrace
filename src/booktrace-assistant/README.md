# BookTrace 小幫手

給不熟悉指令列的使用者使用。畫面就像一般聊天網站：打書名／ISBN，或選擇、拖入、直接貼上書本照片，程式便會呼叫本機的 Codex CLI 或 Claude CLI，依 [查書規則](booktrace_assistant/rules.md) 查證版本、資料來源與封面，經使用者確認後寫入 [BookTrace](https://booktrace.primeeagle.net/)。

## 開始使用

1. 雙擊 [啟動 BookTrace 小幫手.cmd](啟動%20BookTrace%20小幫手.cmd)，會開啟一個命令列視窗並印出網址（例如 `http://192.168.1.20:8765/`）。
2. 用瀏覽器開啟該網址（同一個網址也可以分享給同網路的其他人）。直接輸入書名、ISBN 或一句自然語言。
3. 圖片可以按「＋」選擇、拖進輸入框，或直接按 `Ctrl+V` 貼上；最多四張。若某張就是正面封面，按圖片下方的「這張是封面」。
4. 按 Enter 或右側箭頭送出。查證階段只會查詢，不會改動書架。
   查詢時對話中會出現「查證過程」，點開可以看到 AI 目前在搜尋什麼、開了哪些網頁；輸入框上方也有「查看進度」和已進行的時間。完成後會顯示總步數、耗時與大約花費。
5. 查證完成後，對話中會顯示書籍卡片。看過版本與封面後，按「加入 BookTrace」並確認。

一次想查好幾本：按輸入框旁的「≡」，每一列填一本（書名／ISBN，可各附一張照片，最多 10 本）。小幫手會把送出的每一本同時開始查證（不用排隊），每本都有自己的卡片；某一本失敗或需要補充，不會影響其他本。哪一本先查好、封面也確認了，就可以先按它的「加入 BookTrace」，不用等其他本查完；在候選版本按「就是這本」也會馬上接著查，不用等整批結束。也可以等全部查完後按「全部加入」。按「停止」會停掉所有還在查或排隊中的書，正在加入書架的步驟不會被中斷。

平常不需要看到任何技術選項。若想更換 Codex／Claude 或模型，按右上角的模型名稱或齒輪即可；選擇會記住，下次開啟沿用。

## 關閉

直接關閉命令列視窗（或在視窗內按 `Ctrl+C`），小幫手就會結束。沒有背景程式，也沒有另外的關閉檔。

## 分享給別人

- 啟動後視窗印出的網址（區域網路 IP）可以直接分享，不需要 token 或額外密碼；連接埠預設 `8765`，被占用時可先設定環境變數 `BOOKTRACE_PORT` 換一個。
- 外部連線要通過本機防火牆（Windows 防火牆的輸入規則 TCP `8765`）由你自行設定，通常只開放給內部網路。
- 所有開啟網址的人共用同一個小幫手：同一份對話與書單、同一組 BookTrace 登入（見下方）與同一個 CLI 額度。

## 運作方式

程式採兩階段流程：

1. **查證（唯讀）**：把 [`rules.md`](booktrace_assistant/rules.md) 全文放進提示，交給 Claude／Codex CLI。AI 只能使用網頁搜尋、讀取圖片與 BookTrace 的 `find_book`／`get_book`，回傳符合 [`research_schema.json`](booktrace_assistant/research_schema.json) 的結果。修改 `rules.md` 即可調整 AI 查書的方式。
2. **保存**：使用者按「加入 BookTrace」並再次確認後，介面才以 [`enrich_book.py`](booktrace_assistant/enrich_book.py) 新增或補齊資料、上傳封面，並以 `get_book` 讀回、下載封面比對驗證。

## 模型與費用

- 預設助理為 Claude（兩者都已安裝時）；最後一次在設定中選的助理與模型會記住。
- Codex 預設：`gpt-5.6-luna`（低費率）；可切換 `gpt-5.6-terra`、`gpt-5.6-sol`、`gpt-6-astra` 或 CLI 預設。以 ChatGPT 帳號登入 Codex 時，可用模型以 `codex debug models` 列出的為準。
- 若本機有 `~/.claude-5x` 設定資料夾，會多出「Claude 5x」選項：同一個 `claude` CLI，但改用該資料夾的帳號與額度（啟動時設定 `CLAUDE_CONFIG_DIR`）。
- Claude 預設：`claude-sonnet-5`（平衡）；可切換 Haiku 4.5（最省費用，但實測會從封面照片認錯版本）、Opus、Fable 或 CLI 預設。
- 「思考深度」可選自動、低、中、高、很高、最高（對應 Claude `--effort`、Codex `model_reasoning_effort`）。越深越仔細，但越慢、越花錢；右上角會顯示目前的模型與思考深度。
- 下拉欄位可直接輸入帳號實際可用的模型 ID。若模型不可用，請改選「使用 CLI 預設」。

模型可用性依帳號方案而異。介面的預設選擇依 [OpenAI 模型選擇說明](https://developers.openai.com/api/docs/guides/model-selection) 與 [Claude 模型一覽](https://platform.claude.com/docs/en/models/overview) 設定。

## 自動重試

「自動等待並重試」預設開啟。遇到下列可恢復狀況時，輸入框上方會顯示倒數，並持續重試到完成或使用者按停止：

- 5 小時用量窗或速率限制（429）
- 服務忙碌、502／503／504
- 暫時網路中斷或逾時

登入失敗、模型不存在、圖片格式錯誤、版本歧義等需要人處理的問題不會無限重試。BookTrace 保存若因暫時網路問題中斷，也會沿用 helper 的查重流程安全重試。

## 登入 BookTrace

查書不需要登入，但「加入 BookTrace」會新增資料，要用**和 BookTrace 網站相同的帳號與密碼**登入：

1. 按右上角齒輪，在「BookTrace 登入」輸入帳號與密碼，按「登入」。小幫手會像網站一樣向 BookTrace 登入一次確認，確認可以才會記住。
2. 之後按「加入 BookTrace」就能直接寫入。想換帳號或密碼按「重新登入」，想清除按「登出」。
3. 還沒登入就按「加入 BookTrace」，會直接帶到登入欄位。
4. 網站還沒有建立帳號時，請先到網站建立帳號。**在網站換過密碼後，這裡也要重新登入一次。**

密碼只存在這台電腦的 `.booktrace-ui-settings.json`（已被 Git 忽略），畫面與對話都不會顯示它；也可以改用環境變數 `BOOKTRACE_PASSWORD`（帳號用 `BOOKTRACE_USERNAME`）。寫入時它只會以環境變數交給保存工具，不會出現在命令列，而且只在 HTTPS（或本機網址）下才會送出。查證階段的 AI 只能讀取，不會拿到密碼。

## 第一次使用前

電腦需有 Python 3，以及至少一個已安裝並登入的 CLI：

```powershell
codex login
```

或：

```powershell
claude auth
```

BookTrace MCP 的網址（`https://booktrace.primeeagle.net/mcp`）由程式直接帶給 CLI，不需要另外設定 MCP。

介面只使用 Python 標準函式庫，啟動後監聽所有網卡（`0.0.0.0`）的固定連接埠，**沒有任何存取驗證**，請只在信任的內部網路開放。

## 疑難排解

- 「未偵測到 CLI」：確認 `codex --version` 或 `claude --version` 能在命令提示字元執行。
- 「尚未登入」：先執行上方登入命令，再重開小幫手。
- 「需要你確認版本」：依畫面問題補上封底 ISBN、出版年或版權頁資訊，再按一次查證。
- 「缺少可信封面」：加入單本正面封面照並勾選可作為封面，或補充版本線索後重新查證。

## 單獨使用保存工具

`enrich_book.py` 只用 Python 標準函式庫，也可以不透過介面直接執行（例如其他代理人已查好資料時）：

```powershell
python booktrace_assistant/enrich_book.py --endpoint https://booktrace.primeeagle.net/mcp --metadata book.json --cover cover.jpg
```

寫入前先設定環境變數 `BOOKTRACE_PASSWORD`（見上方「登入 BookTrace」）。

- `book.json` 至少包含 `title` 與實際查證過的 `sources` 網址陣列；其餘欄位見 BookTrace MCP 的 `add_book`。
- 預設只補空欄且保留已有封面；`--correct` 允許更正既有值，`--replace-cover` 替換封面。
- 若保存資料後封面上傳失敗，會回報書籍 ID，可用 `--book-id` 重試，不會建立第二本。

## 開發驗證

在這個資料夾執行：

```powershell
python -m unittest discover -s tests -v
```

| 位置 | 內容 |
| --- | --- |
| `booktrace_assistant/webapp.py` | HTTP 伺服器、對話狀態、設定記憶 |
| `booktrace_assistant/runner.py` | 組 Claude／Codex CLI 指令、解析進度事件、自動重試 |
| `booktrace_assistant/core.py` | 查證提示、結果解析與驗證 |
| `booktrace_assistant/saver.py`、`enrich_book.py` | 確認後寫入 BookTrace 並讀回驗證 |
| `booktrace_assistant/web/` | 聊天介面 |
| `*.cmd` | 雙擊啟動（須維持純 ASCII 與 CRLF 換行） |
