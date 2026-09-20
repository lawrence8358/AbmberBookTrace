import { expect, test, type Page } from "@playwright/test";
import { addBook, expectNoHorizontalOverflow, uniqueTitle, useFixedClock } from "./helpers";

const TODAY = "2026-09-20";
const DEFAULT_DUE_DATE = "2026-10-04";

async function openBorrowingHistory(page: Page) {
  const desktopLink = page.getByRole("link", { name: "借閱歷史", exact: true });
  if ((await desktopLink.count()) > 0 && await desktopLink.first().isVisible()) {
    await desktopLink.first().click();
    return;
  }

  await page.getByRole("link", { name: "歷史", exact: true }).click();
}

test("responsive users can complete the MVP book lifecycle", async ({ page }) => {
  await useFixedClock(page);
  const title = uniqueTitle("響應式 MVP 驗收");
  const borrower = uniqueTitle("驗收借閱人");

  await addBook(page, title, {
    author: "驗收作者",
    location: "房間書櫃",
    detailedLocation: "第二層左側",
  });
  await expectNoHorizontalOverflow(page);

  await page.goto("/books#library-search");
  const search = page.getByRole("searchbox", { name: "搜尋書名、作者或 ISBN" });
  await search.fill(title);
  const result = page.locator(".library-results").getByRole("link", { name: title, exact: true });
  await expect(result).toBeVisible();
  await result.click();

  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
  await expect(page.getByText("房間書櫃", { exact: true })).toBeVisible();
  await expect(page.getByText("第二層左側", { exact: true })).toBeVisible();
  await expect(page.getByText(/在家/).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("button", { name: "借出", exact: true }).click();
  const dueDate = page.getByRole("textbox", { name: /預計歸還日期/ });
  await expect(dueDate).toHaveValue(DEFAULT_DUE_DATE);
  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill(borrower);
  await dueDate.fill(TODAY);
  await page.getByRole("button", { name: "確認借出", exact: true }).click();
  await expect(page.getByText(/借出中/).first()).toBeVisible();
  await expect(page.locator(".borrowing-details").getByText(borrower, { exact: true })).toBeVisible();

  await openBorrowingHistory(page);
  await expect(page.getByRole("heading", { name: "借閱歷史", exact: true })).toBeVisible();
  const currentRecord = page.locator('[data-history-status="CURRENT"]').filter({ hasText: title });
  await expect(currentRecord).toBeVisible();
  await expect(currentRecord.getByText(borrower, { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "提醒", exact: true }).first().click();
  await expect(page.getByRole("heading", { name: "目前提醒", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: title, exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("link", { name: title, exact: true }).click();
  await expect(page.getByRole("button", { name: "已歸還", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "已歸還", exact: true }).click();
  await expect(page.getByText("目前沒有借閱中的資料", { exact: true })).toBeVisible();
  await expect(page.getByText(/在家/).first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
