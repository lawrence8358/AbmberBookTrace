# 書庫視覺對齊

範圍：既有 Vue 全站介面、導覽與共用品牌外框。模式：Operate。2026-09-28 依使用者回饋擴展。
依據：`需求書/視覺設計稿.png`，沿用既有功能與單一中文字體。

## Direction contract

THESIS: 在能快速找書的私人書房裡，恢復原稿的水彩生活感。

OWN-WORLD: 沿用奶油白、鼠尾草綠、珊瑚與柔和藍；水彩貓咪和閱讀女孩為獨立透明插畫。功能文字保持清楚，真實書封不換成裝飾封面。

STORY: 進入書庫、搜尋書名或作者、查看位置與借閱狀態，接著開啟書籍或新增藏書。

FIRST VIEWPORT: 桌面側欄上移並移除新增按鈕，底部閱讀插畫擴至側欄完整寬度；Header 搜尋、通知彈窗與頭像。手機 Header 為左選單、中央品牌、右通知／頭像；設定在選單內。手機底部固定首頁、歷史、新增、提醒、回收筒，新增置中。主要頁面標題頂端對齊，首頁不重複顯示提醒。

FORM: 既有介面的局部延伸，依使用者指定設計稿直接切版；不建立新視覺世界，無 concept seed。圖像只用於迎賓、側欄與空狀態，字句由 HTML 呈現。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## 完成紀錄

- 已接入透明水彩圖，原稿與生成提示保存於 `docs/design/assets/`。
- 初次獨立複查發現手機最近新增過窄；改為單欄後獲得 ship the fix。
- 後續依使用者要求調整全站與五格導覽；子代理因工作區額度不足失敗，最終跨頁檢查及文件同步由主代理完成。
- 桌面 1440 × 800、手機 390 × 800 逐頁檢查；完整證據在 `.impeccable/review/`。
- Header 後續修正：桌面六頁標題均約 105px、手機約 101px；通知用獨立合成資料驗證到期、逾期、錯誤、重試及無通知。標準／較大字級可儲存，手機設定不占底部 Tab。
