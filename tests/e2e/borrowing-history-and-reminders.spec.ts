import { expect, test, type Page } from "@playwright/test";

const FIXED_NOW = "2026-09-20T09:00:00.000Z";
const TODAY = "2026-09-20";
const DEFAULT_DUE_DATE = "2026-10-04";
const OVERDUE_DATE = "2026-09-18";

async function useFixedClock(page: Page) {
  await page.addInitScript(`
    (() => {
      const fixedNow = ${JSON.stringify(FIXED_NOW)};
      const OriginalDate = Date;
      class FixedDate extends OriginalDate {
        constructor(...args) {
          super(...(args.length ? args : [fixedNow]));
        }

        static now() {
          return new OriginalDate(fixedNow).getTime();
        }
      }
      window.Date = FixedDate;
    })();
  `);
}

async function addBook(page: Page, title: string) {
  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill(title);
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
}

async function borrowBook(page: Page, borrowerName: string, dueDate: string | null) {
  await page.getByRole("button", { name: "借出" }).click();
  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill(borrowerName);
  const dueDateInput = page.getByRole("textbox", { name: /預計歸還日期/ });
  if (dueDate === null) {
    await page.getByRole("button", { name: "清除日期" }).click();
  } else {
    await dueDateInput.fill(dueDate);
  }
  await page.getByRole("button", { name: "確認借出" }).click();
  await expect(page.locator(".borrowing-details").getByText(borrowerName, { exact: true })).toBeVisible();
}

test("preserves borrowing history and shows deterministic due and overdue reminders", async ({ page }) => {
  await useFixedClock(page);

  const returnedTitle = "歷史保存測試書";
  await addBook(page, returnedTitle);
  await page.getByRole("button", { name: "借出" }).click();
  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill("小美");
  await expect(page.getByRole("textbox", { name: /預計歸還日期/ })).toHaveValue(DEFAULT_DUE_DATE);
  await page.getByRole("textbox", { name: /預計歸還日期/ }).fill(TODAY);
  await page.getByLabel("借出備註", { exact: true }).fill("歷史備註");
  await page.getByRole("button", { name: "確認借出" }).click();
  await expect(page.locator('[data-history-status="CURRENT"]')).toBeVisible();

  await page.getByRole("link", { name: "借閱歷史", exact: true }).click();
  const currentHistory = page.locator('[data-history-status="CURRENT"]').filter({ hasText: returnedTitle });
  await expect(currentHistory).toBeVisible();
  await expect(currentHistory.getByText("小美", { exact: true })).toBeVisible();
  await expect(currentHistory.getByText("歷史備註", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: returnedTitle, exact: true }).click();
  await page.getByRole("button", { name: "已歸還" }).click();
  await expect(page.getByText("目前沒有借閱中的資料", { exact: true })).toBeVisible();
  await expect(page.locator('[data-history-status="RETURNED"]')).toBeVisible();
  await expect(page.locator('[data-history-status="RETURNED"]').getByText("已歸還", { exact: true })).toBeVisible();

  await addBook(page, "今天到期提醒書");
  await borrowBook(page, "小王", TODAY);
  await addBook(page, "逾期提醒書");
  await borrowBook(page, "小林", OVERDUE_DATE);
  await addBook(page, "無期限借閱書");
  await borrowBook(page, "小陳", null);

  await page.getByRole("link", { name: "提醒", exact: true }).click();
  await expect(page.getByRole("heading", { name: "目前提醒" })).toBeVisible();
  await expect(page.getByText("今天到期", { exact: true })).toBeVisible();
  await expect(page.getByText("逾期通知", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "今天到期提醒書", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "逾期提醒書", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "無期限借閱書", exact: true })).toHaveCount(0);
  await expect(page.getByText(/已逾期 2 天/)).toBeVisible();

  await page.getByRole("link", { name: "我的書庫", exact: true }).click();
  await expect(page.getByRole("heading", { name: "借閱提醒" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看全部提醒 →", exact: true })).toBeVisible();

  await page.getByRole("link", { name: "借閱歷史", exact: true }).click();
  await expect(page.locator('[data-history-status="RETURNED"]').filter({ hasText: returnedTitle })).toBeVisible();
  await expect(page.locator('[data-history-status="CURRENT"]').filter({ hasText: "無期限借閱書" })).toBeVisible();
});
