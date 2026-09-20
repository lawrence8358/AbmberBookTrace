import { expect, test } from "@playwright/test";
import { useFixedClock } from "./helpers";

test.describe.configure({ mode: "serial" });

const validPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

test("desktop user can add, replace, remove, and persist a book cover", async ({ page }) => {
  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill("封面測試書籍");

  await page.locator("#new-book-cover-gallery-input").setInputFiles({
    name: "first-cover.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await expect(page.getByAltText("書籍封面預覽")).toBeVisible();

  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  const cover = page.locator(".cover-card img");
  await expect(cover).toBeVisible();
  const firstCoverUrl = await cover.getAttribute("src");

  await page.reload();
  await expect(page.locator(".cover-card img")).toBeVisible();

  await page.locator("#detail-book-cover-gallery-input").setInputFiles({
    name: "replacement-cover.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await expect(page.getByText("封面已更新。", { exact: true })).toBeVisible();
  await expect(page.locator(".cover-card img")).toHaveAttribute("src", /v=/);
  const replacementCoverUrl = await page.locator(".cover-card img").getAttribute("src");
  expect(replacementCoverUrl).not.toBe(firstCoverUrl);

  await page.getByRole("button", { name: "移除封面" }).click();
  await expect(page.getByText("封面已移除。", { exact: true })).toBeVisible();
  await expect(page.locator(".cover-card img")).toHaveCount(0);

  await page.reload();
  await expect(page.getByText("尚未上傳封面")).toBeVisible();
});

test("replacing a cover keeps current borrowing details on the detail page", async ({ page }) => {
  await useFixedClock(page);
  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill("借出中封面替換測試書");
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);

  const bookId = Number(new URL(page.url()).pathname.split("/").pop());
  const borrowResponse = await page.request.post(`/api/books/${bookId}/borrow`, {
    data: {
      borrowerName: "封面替換借閱人",
      dueDate: "2026-10-04",
      note: "封面替換時仍應保留",
      clearDueDate: false,
    },
  });
  expect(borrowResponse.ok()).toBeTruthy();
  await page.reload();

  await page.locator("#detail-book-cover-gallery-input").setInputFiles({
    name: "borrowed-book-cover.png",
    mimeType: "image/png",
    buffer: validPng,
  });

  await expect(page.getByText("封面已更新。", { exact: true })).toBeVisible();
  const currentBorrowingDetails = page.locator(".borrowing-details");
  await expect(currentBorrowingDetails.getByText("封面替換借閱人", { exact: true })).toBeVisible();
  await expect(currentBorrowingDetails.getByText("2026/10/4", { exact: true })).toBeVisible();
});

test("desktop user receives understandable cover validation errors", async ({ page }) => {
  await page.goto("/books/new");
  const input = page.locator("#new-book-cover-gallery-input");

  await input.setInputFiles({
    name: "not-an-image.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not an image"),
  });
  await expect(page.getByText("封面只接受 JPG、PNG、GIF 或 WebP 圖片。", { exact: true })).toBeVisible();

  await input.setInputFiles({
    name: "too-large.png",
    mimeType: "image/png",
    buffer: Buffer.alloc(5 * 1024 * 1024 + 1),
  });
  await expect(page.getByText("封面圖片不可超過 5 MB。", { exact: true })).toBeVisible();
});

test("mobile user can choose a gallery image or use the camera input", async ({ page }) => {
  await page.goto("/books/new");

  const galleryInput = page.locator("#new-book-cover-gallery-input");
  const cameraInput = page.locator("#new-book-cover-camera-input");
  await expect(galleryInput).toHaveAttribute("accept", "image/jpeg,image/png,image/gif,image/webp");
  await expect(cameraInput).toHaveAttribute("capture", "environment");

  await galleryInput.setInputFiles({
    name: "gallery-cover.png",
    mimeType: "image/png",
    buffer: validPng,
  });
  await expect(page.getByAltText("書籍封面預覽")).toBeVisible();

  await cameraInput.setInputFiles({
    name: "camera-cover.jpg",
    mimeType: "image/jpeg",
    buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
  });
  await expect(page.getByAltText("書籍封面預覽")).toBeVisible();

  await page.getByLabel("書名（必填）", { exact: true }).fill("手機封面測試書籍");
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  await expect(page.locator(".cover-card img")).toBeVisible();
});
