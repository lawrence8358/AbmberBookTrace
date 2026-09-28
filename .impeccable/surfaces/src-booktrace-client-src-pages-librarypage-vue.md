---
version: 1
slug: "src-booktrace-client-src-pages-librarypage-vue"
primary_target: "src/booktrace-client/src/pages/LibraryPage.vue"
related_targets: ["src/booktrace-client/src/App.vue","src/booktrace-client/src/style.css","src/booktrace-client/src/components/PageHeading.vue"]
---

# 書庫視覺對齊

範圍：既有 Vue 全站介面、導覽與共用品牌外框。模式：Operate。2026-09-28 依使用者回饋擴展。
依據：`需求書/視覺設計稿.png`，沿用既有功能與單一中文字體。

## Direction contract

THESIS: 在能快速找書的私人書房裡，恢復原稿的水彩生活感。

OWN-WORLD: 沿用奶油白、鼠尾草綠、珊瑚與柔和藍；水彩貓咪和閱讀女孩為獨立透明插畫。功能文字保持清楚，真實書封不換成裝飾封面。

STORY: 進入書庫、搜尋書名或作者、查看位置與借閱狀態，接著開啟書籍或新增藏書。

FIRST VIEWPORT: 桌面左側四個選單上移並移除新增按鈕，底部閱讀插畫擴至側欄完整寬度；頂部保留提醒與頭像。書庫迎賓下方搜尋、橫向統計與有封面的最近新增。手机底部固定首頁、歷史、新增、提醒、回收筒，新增置中。功能頁共用小幅貓咪標題區與相同卡片語言。

FORM: 既有介面的局部延伸，依使用者指定設計稿直接切版；不建立新視覺世界，無 concept seed。圖像只用於迎賓、側欄與空狀態，字句由 HTML 呈現。

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## 完成紀錄

- 已接入透明水彩圖，原稿與生成提示保存於 `docs/design/assets/`。
- 初次獨立複查發現手機最近新增過窄；改為單欄後獲得 ship the fix。
- 後續依使用者要求調整全站與五格導覽；子代理因工作區額度不足失敗，最終跨頁檢查及文件同步由主代理完成。
- 桌面 1440 × 800、手機 390 × 800 逐頁檢查；完整證據在 `.impeccable/review/`。
