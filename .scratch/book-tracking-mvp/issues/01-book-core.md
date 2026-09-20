# 01: 建立書籍核心流程

**What to build:** 建立可執行的「書蹤」私人書庫，讓使用者可以新增一本書、保存基本資料、在書庫中看到它，並開啟書籍詳細資料。這張 ticket 完成後，使用者已經能走完第一條可展示的「新增書籍 → 查看書籍」流程。

**Blocked by:** None (can start immediately)

**Status:** resolved

**Labels:** ready-for-agent

- [x] 應用程式可以使用 Vue 3、ASP.NET Core Web API、SQLite 與 EF Core 啟動並保存資料。
- [x] 使用者可以新增書籍；書名必填，作者、ISBN、出版社、分類／標籤、位置、詳細位置與備註選填。
- [x] 新增書籍時狀態預設為「在家」，並允許書名或 ISBN 重複。
- [x] 書庫可以顯示書名、作者、位置與狀態，並可開啟單一本書的詳細資料。
- [x] 空書庫與書名驗證失敗時，畫面會顯示清楚的下一步提示。
- [x] 有瀏覽器流程測試驗證「新增書籍 → 書庫出現 → 開啟詳細資料」。

## Comments

- 2026-09-20：依使用者確認的 `book-tracking-mvp` ticket 拆分發布。
- 2026-09-20：開始依交接規格實作；測試 seam 採完整瀏覽器流程，先完成新增書籍到查看詳情的 tracer bullet。
- 2026-09-20：完成 Vue／ASP.NET Core／SQLite 核心流程與瀏覽器驗收；修正狀態 badge 動態呈現並完成 code review。
