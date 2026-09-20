# 問題追蹤方式：本機 Markdown

這個專案的問題和規格，都會用 Markdown 檔案放在 `.scratch/` 裡。

## 檔案規則

- 每個功能使用一個資料夾：`.scratch/<feature-slug>/`
- 規格檔是：`.scratch/<feature-slug>/spec.md`
- 每張實作問題單都放在：
  `.scratch/<feature-slug>/issues/<NN>-<slug>.md`
- 問題單從 `01` 開始編號，不要把所有問題合在同一個檔案
- 每張問題單上方要有 `Status:`，表示目前的處理狀態
- 對話和留言要加在檔案最下面的 `## Comments` 標題下

## 技能說「發布到問題追蹤系統」時

請在 `.scratch/<feature-slug>/` 裡建立新檔案。需要時可以先建立資料夾。

## 技能說「取得相關問題單」時

請讀取指定的檔案。通常使用者會提供檔案路徑或問題編號。

## Wayfinder 的操作方式

`/wayfinder` 會使用這些規則：

- **地圖檔**：`.scratch/<effort>/map.md`
- **子問題檔**：`.scratch/<effort>/issues/NN-<slug>.md`
- 子問題檔要從 `01` 開始編號，問題寫在檔案內容裡
- `Type:` 表示問題類型，可以是 `research`、`prototype`、`grilling` 或 `task`
- `Status:` 可以是 `claimed` 或 `resolved`
- `Blocked by:` 表示這張問題單要等哪些問題單完成
- 所有被列出的問題單都完成後，這張問題單才算可以處理
- 找出還沒完成、沒有被卡住、也還沒被認領的問題單，優先處理編號最小的那張
- **認領**：先把 `Status:` 改成 `claimed`，再開始工作
- **完成**：在 `## Answer` 下寫答案，把 `Status:` 改成 `resolved`，再把重要內容記回 `map.md`
