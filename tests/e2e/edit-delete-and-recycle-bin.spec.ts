import { expect, test } from "@playwright/test";

const validPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

function uniqueTitle(prefix: string) {
  return `${prefix} ${Date.now()}`;
}

test("desktop user can edit every book field, delete with confirmation, and restore history", async ({ page }) => {
  const originalTitle = uniqueTitle("可還原書籍");
  const updatedTitle = uniqueTitle("編輯後書籍");

  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill(originalTitle);
  await page.getByLabel("作者", { exact: true }).fill("原作者");
  await page.getByLabel("ISBN", { exact: true }).fill("ISBN-ORIGINAL");
  await page.getByLabel("出版社", { exact: true }).fill("原出版社");
  await page.getByLabel("分類／標籤", { exact: true }).fill("原分類");
  await page.getByLabel("位置", { exact: true }).fill("原位置");
  await page.getByLabel("詳細位置", { exact: true }).fill("原詳細位置");
  await page.getByLabel("備註", { exact: true }).fill("原備註");
  await page.locator("#new-book-cover-gallery-input").setInputFiles({
    name: "original-cover.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/(\d+)$/);
  const bookId = Number(new URL(page.url()).pathname.split("/").at(-1));

  await page.getByRole("button", { name: "修改資料" }).click();
  await expect(page).toHaveURL(`/books/${bookId}/edit`);
  await expect(page.getByAltText("書籍封面預覽")).toBeVisible();
  await page.getByLabel("書名（必填）", { exact: true }).fill(updatedTitle);
  await page.getByLabel("作者", { exact: true }).fill("新作者");
  await page.getByLabel("ISBN", { exact: true }).fill("ISBN-UPDATED");
  await page.getByLabel("出版社", { exact: true }).fill("新出版社");
  await page.getByLabel("分類／標籤", { exact: true }).fill("新分類");
  await page.getByLabel("位置", { exact: true }).fill("新位置");
  await page.getByLabel("詳細位置", { exact: true }).fill("新詳細位置");
  await page.getByLabel("備註", { exact: true }).fill("新備註");
  await page.locator("#edit-book-cover-gallery-input").setInputFiles({
    name: "updated-cover.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await page.getByRole("button", { name: "儲存修改" }).click();

  await expect(page).toHaveURL(`/books/${bookId}`);
  await expect(page.getByRole("heading", { name: updatedTitle, exact: true })).toBeVisible();
  await expect(page.getByText("新作者", { exact: true })).toBeVisible();
  await expect(page.getByText("ISBN-UPDATED", { exact: true })).toBeVisible();
  await expect(page.getByText("新出版社", { exact: true })).toBeVisible();
  await expect(page.getByText("新分類", { exact: true })).toBeVisible();
  await expect(page.getByText("新位置", { exact: true })).toBeVisible();
  await expect(page.getByText("新詳細位置", { exact: true })).toBeVisible();
  await expect(page.getByText("新備註", { exact: true })).toBeVisible();
  await expect(page.locator(".cover-card img")).toBeVisible();

  await page.getByRole("button", { name: "借出" }).click();
  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill("歷史借閱人");
  await page.getByRole("button", { name: "確認借出" }).click();
  await page.getByRole("button", { name: "已歸還" }).click();
  await expect(page.locator('[data-history-status="RETURNED"]')).toBeVisible();

  const statsBeforeDelete = await page.request.get("/api/books/stats");
  const beforeDelete = await statsBeforeDelete.json();
  const deleteDialogMessages: string[] = [];
  page.once("dialog", async (dialog) => {
    deleteDialogMessages.push(dialog.message());
    await dialog.dismiss();
  });
  await page.getByRole("button", { name: "刪除書籍" }).click();
  expect(deleteDialogMessages[0]).toContain(updatedTitle);
  await expect(page.getByRole("heading", { name: updatedTitle, exact: true })).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "刪除書籍" }).click();
  await expect(page).toHaveURL("/books");
  await expect(page.getByRole("heading", { name: updatedTitle, exact: true })).toHaveCount(0);
  await expect(page.locator(".library-results").getByText(updatedTitle, { exact: true })).toHaveCount(0);

  const statsAfterDelete = await page.request.get("/api/books/stats");
  const afterDelete = await statsAfterDelete.json();
  expect(afterDelete.totalCount).toBe(beforeDelete.totalCount - 1);

  await page.getByRole("link", { name: "資源回收筒", exact: true }).click();
  await expect(page.getByRole("heading", { name: "資源回收筒", exact: true })).toBeVisible();
  const recycleCard = page.locator(".recycle-card").filter({ hasText: updatedTitle });
  await expect(recycleCard).toBeVisible();
  await expect(recycleCard.getByText(/\d+ 天內可還原/, { exact: true })).toBeVisible();

  await recycleCard.getByRole("button", { name: "還原書籍" }).click();
  await expect(page).toHaveURL(`/books/${bookId}`);
  await expect(page.getByRole("heading", { name: updatedTitle, exact: true })).toBeVisible();
  await expect(page.locator(".cover-card img")).toBeVisible();
  await expect(page.locator('[data-history-status="RETURNED"]')).toContainText("歷史借閱人");

  const statsAfterRestore = await page.request.get("/api/books/stats");
  const afterRestore = await statsAfterRestore.json();
  expect(afterRestore.totalCount).toBe(beforeDelete.totalCount);
});

test("mobile users do not see edit and delete controls", async ({ page }) => {
  const title = uniqueTitle("手機隱藏操作");
  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill(title);
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole("button", { name: "修改資料" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "刪除書籍" })).toHaveCount(0);
});

test("expired deleted books are permanently cleaned up", async ({ page }) => {
  const title = uniqueTitle("逾期清理書籍");
  const createResponse = await page.request.post("/api/books", { data: { title } });
  expect(createResponse.ok()).toBeTruthy();
  const book = await createResponse.json();

  const deleteResponse = await page.request.delete(`/api/books/${book.id}`);
  expect(deleteResponse.ok()).toBeTruthy();
  const ageResponse = await page.request.post(`/api/test/recycle-bin/${book.id}/age`, {
    data: { daysAgo: 31 },
  });
  expect(ageResponse.ok()).toBeTruthy();

  const recycleResponse = await page.request.get("/api/recycle-bin");
  expect(recycleResponse.ok()).toBeTruthy();
  const recycleBin = await recycleResponse.json();
  expect(recycleBin.some((item: { id: number }) => item.id === book.id)).toBeFalsy();

  const restoreResponse = await page.request.post(`/api/recycle-bin/${book.id}/restore`);
  expect(restoreResponse.status()).toBe(404);
});
