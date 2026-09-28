import { expect, test } from "@playwright/test";

test("book dates can be created, edited, cleared and reloaded", async ({ page }) => {
  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill("日期欄位測試");
  await page.getByLabel("出版日期", { exact: true }).fill("2020-02-29");
  await page.getByLabel("購入日期", { exact: true }).fill("2026-09-28");
  await page.getByRole("button", { name: "儲存書籍", exact: true }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  const bookUrl = page.url();
  await expect(page.getByText("2020-02-29", { exact: true })).toBeVisible();
  await expect(page.getByText("2026-09-28", { exact: true })).toBeVisible();
  await page.goto(`${bookUrl}/edit`);
  await expect(page.getByLabel("出版日期", { exact: true })).toHaveValue("2020-02-29");
  await expect(page.getByLabel("購入日期", { exact: true })).toHaveValue("2026-09-28");
  await page.getByLabel("出版日期", { exact: true }).fill("2021-01-01");
  await page.getByLabel("購入日期", { exact: true }).fill("");
  await page.getByRole("button", { name: "儲存修改", exact: true }).click();
  await expect(page).toHaveURL(bookUrl);
  await page.reload();
  await expect(page.getByText("2021-01-01", { exact: true })).toBeVisible();
  await expect(page.locator(".metadata-list > div").filter({ has: page.locator("dt", { hasText: "購入日期" }) }).getByRole("definition")).toHaveText("未記錄");
});
