import { expect, test } from "@playwright/test";

test("user can add a book and open its details", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "目前還沒有藏書" })).toBeVisible();

  await page.getByRole("link", { name: "新增書籍", exact: true }).click();
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page.getByText("請輸入書名，才能保存這本書。"))
    .toBeVisible();

  await page.getByLabel("書名（必填）", { exact: true }).fill("夜航西飛");
  await page.getByLabel("作者", { exact: true }).fill("柏瑞爾・馬卡姆");
  await page.getByLabel("位置", { exact: true }).fill("客廳書櫃");
  await page.getByLabel("詳細位置", { exact: true }).fill("第二層左側");
  await page.getByRole("button", { name: "儲存書籍" }).click();

  await expect(page).toHaveURL(/\/books\/\d+$/);
  await expect(page.getByRole("heading", { name: "夜航西飛" })).toBeVisible();
  await expect(page.getByText("柏瑞爾・馬卡姆")).toBeVisible();
  await expect(page.getByText("客廳書櫃", { exact: true })).toBeVisible();
  await expect(page.getByText("第二層左側", { exact: true })).toBeVisible();
  await expect(page.getByText("在家")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "夜航西飛" })).toBeVisible();
  await expect(page.getByText("客廳書櫃", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "我的書庫", exact: true }).click();
  await expect(page.getByRole("link", { name: "夜航西飛" })).toBeVisible();
});
