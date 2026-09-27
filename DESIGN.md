---
name: 書蹤 (BookTrace)
description: 找到我的每一本書 —— 溫暖、清爽、帶有閱讀與手帳感的私人藏書空間
colors:
  primary: "#8CB69B"
  primary-hover: "#729B81"
  primary-light: "#EAF3ED"
  warm-accent: "#F4A896"
  warm-accent-light: "#FDF0EC"
  cool-accent: "#A7C7E2"
  cool-accent-light: "#F0F6FA"
  bg-cream: "#FFF9F1"
  surface-card: "#FFFFFF"
  text-main: "#5B5B5B"
  text-muted: "#8E8E8E"
  text-light: "#B0A89F"
  border-soft: "#EBE3D7"
  status-home: "#8CB69B"
  status-borrowed: "#F4A896"
  status-returned: "#8E8E8E"
  danger: "#E57373"
  danger-bg: "#FDEAEA"
typography:
  display:
    fontFamily: ""Noto Sans TC", "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", sans-serif"
    fontWeight: 600
    lineHeight: 1.35
  heading:
    fontFamily: ""Noto Sans TC", "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", sans-serif"
    fontWeight: 600
    lineHeight: 1.45
  body:
    fontFamily: ""Noto Sans TC", "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", sans-serif"
    fontWeight: 400
    lineHeight: 1.6
  caption:
    fontFamily: ""Noto Sans TC", "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", sans-serif"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "10px"
  lg: "16px"
  xl: "24px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.primary}"
    rounded: "{rounded.md}"
    padding: "10px 20px"
  button-danger:
    backgroundColor: "{colors.danger-bg}"
    textColor: "{colors.danger}"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  card-book:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input-search:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.text-main}"
    rounded: "{rounded.full}"
    padding: "14px 24px"
  badge-home:
    backgroundColor: "{colors.primary-light}"
    textColor: "{colors.primary}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
  badge-borrowed:
    backgroundColor: "{colors.warm-accent-light}"
    textColor: "{colors.warm-accent}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
---

# Design System

<!-- impeccable:design-schema 1 -->

## Overview

「書蹤」的設計核心是打造一個**溫暖、清爽、帶有閱讀與手帳感**的個人私人書房。

整體視覺避免傳統公立圖書館管理系統的冰冷與繁複規條，改以生活化、溫柔的木質調與紙質氛圍包覆。使用者打開介面時，感受到的是沈靜、安心與愛書之人的專屬秩序。

核心設計法則：
1. **溫暖手帳質感**：大量使用米白與奶油白（`#FFF9F1`），減低純白螢幕的刺眼生硬。
2. **植物綠的沈靜主色**：以柔和的鼠尾草綠（`#8CB69B`）為基底，象徵自然、平靜與知識的生長。
3. **鮮明的溫暖警示**：以珊瑚橘（`#F4A896`）標示「借出中」等動態狀態，既有提醒作用又不破壞整體溫潤調性。
4. **功能頁簡潔，品牌頁溫暖**：品牌插畫與情境圖用於首頁迎賓與空狀態，書籍管理核心操作頁面則注重高效、清楚與充足呼吸感。

---

## Colors

全站色彩規劃緊扣自然植物、米紙與手帳水彩基調：

### 主題色彩角色

| 色彩角色 | 色碼 | 用途說明 |
|---|---|---|
| **主背景（Cream）** | `#FFF9F1` | 全站主要背景色，提供紙張般的溫潤暖意 |
| **卡片背景（Surface）** | `#FFFFFF` | 卡片、輸入框等前景容器，與奶油底形成微對比 |
| **主色（Primary Sage）** | `#8CB69B` | 主要按鈕、Logo重點、選中狀態、在館狀態 |
| **主色懸停（Primary Hover）** | `#729B81` | 主按鈕 Hover 與 Active 狀態 |
| **主色淺底（Primary Light）** | `#EAF3ED` | 「在家」狀態標籤背景、選取背景 |
| **暖色警示（Coral Accent）** | `#F4A896` | 「借出中」狀態標籤、催還備註、重點提醒 |
| **暖色淺底（Coral Light）** | `#FDF0EC` | 「借出中」標籤背景 |
| **輔助冷色（Soft Blue）** | `#A7C7E2` | 輔助標籤、出版社資訊、次要分類 |
| **主文字（Text Main）** | `#5B5B5B` | 書名、主要文字，避免全黑 `#000000` 造成的過強反差 |
| **次要文字（Text Muted）** | `#8E8E8E` | 作者、位置、日期等中階資訊，以及已歸還狀態標籤 |
| **邊框線（Border Soft）** | `#EBE3D7` | 溫和的格線與卡片細邊框 |
| **危險操作（Danger）** | `#E57373` | 刪除書籍按鈕文字與警告邊框 |
| **危險淺底（Danger Light）** | `#FDEAEA` | 刪除按鈕背景 |

---

## Typography

字體排印遵循「**全站只用一種中文字體**，層次完全交給字級與字重」的原則，避免同一頁出現兩種中文字型造成的視覺雜訊。

### 字族設定 (Font Family)

全站唯一字族：

```
"Noto Sans TC", "Microsoft JhengHei", -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC", sans-serif
```

- 標題、書名、內文、按鈕、表單、狀態標籤——**全部**使用這一組，不另外搭配襯線體。
- `Noto Sans TC` 由 `index.html` 以 Google Fonts 載入（400/500/600/700，`display=swap`）；`Microsoft JhengHei`（微軟正黑體）為 Windows 的第一順位備援，其後才是 macOS／iOS 的系統字型，確保沒有網路時各平台也不會各挑各的中文字體。

### 字體設定方式 (Implementation)

- **全站只有一處 `font-family` 宣告**，就在 `style.css` 的 `:root`；其餘所有元素一律靠繼承。
- 任何頁面、元件、卡片都**不得**再寫 `font-family`（包含 `h1`~`h6`、書名、統計數字）。要做出層次請改 `font-size` 與 `font-weight`。
- `button`、`input`、`textarea` 以 `font: inherit` 接上同一套字體，表單不會掉回瀏覽器預設字型。

### 字級階層 (Type Scale)

字族一致，層次靠字級與字重區分：

- **Page Title**: `28px ~ 36px` / 600
- **Section Heading**: `20px ~ 24px` / 600
- **Book Title (Card)**: `16px ~ 19px` / 600
- **Body & Controls**: `14px ~ 16px` / 400
- **Metadata & Badges**: `12px ~ 13px` / 400 ~ 600

---

## Layout

網站採響應式網頁設計（RWD），針對 PC 與手機使用者情境做佈局最佳化：

### PC 電腦版佈局

- **左右雙欄架構**：
  - **左側固定導覽列（Sidebar，寬度 240px）**：包含品牌 Logo、導航選單（首頁、我的書庫、新增書籍、設定）。
  - **主要內容區（Main Content）**：
    - 頂部置中或顯眼的快速搜尋列。
    - 首頁統計卡（藏書總數 128 本、在家 125 本、借出中 3 本）。
    - 內容區採用卡片網格（Card Grid），每列 3～4 欄展示書籍。
  - **右側或懸浮操作**：快速新增與批次整理。

### 手機版佈局

- **單欄直向流動佈局**：
  - **頂部 Header**：輕量化 Logo + 溫暖問候語。
  - **快速搜尋區**：常駐頂部的大圓角搜尋框，支援即時比對。
  - **狀態快篩分頁標籤**：`[ 全部 ]` `[ 在家 ]` `[ 借出中 ]` 水平滑動 Pills。
  - **單欄書籍列表**：每本書以橫向卡片呈現（左側封面/佔位圖，右側書名、作者、位置與狀態 Badge）。
  - **底部固定導覽列（Bottom Navigation Bar）**：
    - 首頁 / 搜尋 / 新增（中央突起高亮）/ 書庫 / 設定。

### 防止內容撐爆版面 (Overflow Rules)

過長的書名是最常見的破版來源，以下規則全站適用：

- 所有 Grid 容器的軌道一律寫 `minmax(0, 1fr)`，不要只寫 `1fr` 或省略 `grid-template-columns`；預設的 `auto` 軌道會被 max-content 撐開，整張卡片就會超出版面。
- 巢狀 Flex 容器每一層都要 `min-width: 0`，截斷才會生效。
- 直向排列（手機版 `flex-direction: column`）要用 `align-items: stretch`；用 `flex-start` 會讓子項目以 max-content 寬度計算而撐破卡片。
- 按鈕與狀態標籤加 `white-space: nowrap` 並設為不可壓縮，長標題不能把它們擠成直排。

---

## Elevation & Depth

「書蹤」摒棄生硬厚重的陰影，採用極柔和的層次：

- **平整紙張基底**：背景使用 `#FFF9F1`。
- **低浮力卡片陰影**：
  `box-shadow: 0 2px 10px rgba(140, 182, 155, 0.08), 0 1px 3px rgba(0, 0, 0, 0.03);`
  陰影帶有極輕微的綠系色偏，使白色卡片與米色底自然交融。
- **卡片懸停 (Hover State)**：
  `transform: translateY(-2px); box-shadow: 0 6px 16px rgba(140, 182, 155, 0.14);`
- **對話框與下拉選單**：
  `box-shadow: 0 12px 28px rgba(91, 91, 91, 0.12);`

---

## Shapes

全站大量採用自然柔和的圓角語彙：

- **大圓角膠囊 (Pill / Full `9999px`)**：
  - 頂部全站搜尋框（Search Bar）
  - 狀態標籤（● 在家 / ● 借出中 / ● 已歸還）
  - 篩選按鈕（Filter Chips）
- **中大圓角 (`12px ~ 16px`)**：
  - 書籍資訊卡（Book Cards）
  - 書籍封面圖（Book Covers）
  - 模態對話框（Modals / Dialogs）
- **標準圓角 (`8px ~ 10px`)**：
  - 操作按鈕（Primary / Secondary Buttons）
  - 表單輸入框（Form Inputs）

---

## Components

### 1. 搜尋列 (Search Input)
- 外觀：大圓角 Pill 造型、米白/白底、左側放大鏡 Icon、右側清除按鈕。
- 佔位提示（Placeholder）：`搜尋書名、作者、ISBN...`
- Focus：柔和綠細邊框（`1.5px solid #8CB69B`）與輕微柔光擴散。

### 2. 狀態標籤 (Status Badge)
- **在家 (HOME)**：
  - 背景：`#EAF3ED`
  - 文字與圓點：`#8CB69B`
  - 內容：`● 在家`
- **借出中 (BORROWED)**：
  - 背景：`#FDF0EC`
  - 文字與圓點：`#F4A896`
  - 內容：`● 借出中`
- **已歸還 (RETURNED)**：
  - 背景：`#F0F0F0`
  - 文字與圓點：`#8E8E8E`
  - 內容：`● 已歸還`

### 3. 書籍資訊卡片 (Book Card)
- 佈局：
  - 左側/上方：精緻書籍封面或溫暖手繪感書本 Icon。
  - 右側/主體：
    - 書名（Serif 粗體，單行截斷；超出以 `…` 呈現，並以 `title` 屬性保留完整書名）
    - 作者（次要文字）
    - 位置資訊：`📍 房間書櫃 · 第二層左邊`（重要醒目標籤）
    - 狀態標籤（右下或右上）
- 借出狀態特別呈現：若為「借出中」，清楚標示 `借給：小美 (2026/09/15)`。

### 4. 統計資訊卡 (Stat Counter Card)
- 呈現數字與說明：`📚 我的藏書 128`、`🏠 在家 125`、`👤 借出中 3`。
- 大字號數字搭配手繪風圖標，字體溫潤。

### 5. 操作按鈕 (Buttons)
- **主要操作 (Primary)**：鼠尾草綠背景、白字、圓角、微陰影（用於「新增書籍」、「借出給同學」、「儲存」）。
- **次要操作 (Secondary)**：白底、綠色外框與綠字（用於「編輯資料」、「返回」）。
- **危險操作 (Danger)**：淡粉紅背景 `#FDEAEA`、紅色文字 `#E57373`（用於 PC 端「刪除書籍」，避免過於突兀誘發誤按）。

---

## Iconography

圖示分成兩種角色，不要互相取代：

### 1. 功能性圖示 (Functional Icons)

介面上表達操作或資料意義的小圖示，一律使用元件 `components/AppIcon.vue` 的內嵌 SVG：

- 規格：`viewBox="0 0 24 24"`、線條式（`fill="none"`、`stroke-width: 1.8`、圓端點）、顏色一律 `currentColor`，尺寸預設 `1.05em` 跟著文字大小縮放。
- 目前提供：`location`（書籍位置）、`search`（搜尋框）、`chevron`（展開／收合）、`clock`（今天到期）、`alert`（逾期）。
- 新增圖示時加在 `AppIcon.vue` 的 `name` 聯集裡，不要在頁面裡直接寫 SVG，也不要用 `⌖`、`⌕`、`›` 這類符號字元充當圖示（各平台字型差異大且無法對齊）。
- 不額外載入 icon font：專案已採內嵌 SVG，集中在單一元件即可達到一致性，也省下一份字型檔的下載。

### 2. 情境插畫 (Illustrative Icons)

帶有手帳溫度、用來營造氣氛的圖像，維持 emoji／插畫風格，不要換成線條 SVG：

- 統計資訊卡：`📚 藏書總數`、`🏠 在家`、`👤 借出中`。
- 空狀態插圖：`📚`、`🌿`、`📝` 等大尺寸圖像。

---

## Do's and Don'ts

### Do's (建議做法)
- **DO** 維持溫暖像「私人書房」的個人感，多用米白、鼠尾草綠與溫潤珊瑚橘。
- **DO** 永遠把「位置資訊（哪間房、哪層櫃）」放在最醒目、最容易看到的地方，因為找書是產品的靈魂。
- **DO** 確保手機與 PC 兩端有統一的色彩標籤語言，一眼能分辨書在不在家。
- **DO** 在首頁迎賓區、空狀態（如「目前還沒有藏書」）放置具手帳質感的溫暖插畫與親切文案。
- **DO** 字體只在 `:root` 設定一次，新元件靠繼承取得字型。

### Don'ts (避免做法)
- **DON'T** 使用高飽和度、冰冷的純藍或純紅，也不要使用未經調和的純黑 `#000000` 與純白冷光。
- **DON'T** 把介面設計成大型圖書館的借書證檢索終端機（如大量密集灰底表格與冰冷代號）。
- **DON'T** 在實際操作與搜尋結果列表中塞滿裝飾插圖，干擾使用者的閱讀與找書視線。
- **DON'T** 讓過長的書名把同一列的按鈕或狀態標籤擠變形；書名一律單行截斷，操作區維持不可壓縮。
- **DON'T** 讓「刪除」按鈕以大紅高對比奪走視覺重心，增加誤觸風險。
- **DON'T** 在任何元件裡另外宣告 `font-family`，也不要混用襯線體與黑體。
