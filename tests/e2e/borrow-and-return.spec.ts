import { expect, test } from "@playwright/test";
import { addBook, uniqueTitle, useFixedClock } from "./helpers";

function addDays(date: Date, days: number) {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result.toISOString().slice(0, 10);
}

function addUtcDays(value: string, days: number) {
  const result = new Date(value);
  result.setUTCDate(result.getUTCDate() + days);
  return result.toISOString().slice(0, 10);
}

test("user can borrow a book, see current borrowing details, and return it", async ({ page }) => {
  const title = uniqueTitle("借閱流程測試");
  await addBook(page, title, { location: "客廳書櫃" });

  await expect(page.getByRole("heading", { name: "借閱狀態" })).toBeVisible();
  await page.getByRole("button", { name: "借出" }).click();
  await expect(page.getByRole("heading", { name: "借出書籍" })).toBeVisible();

  await page.getByRole("button", { name: "確認借出" }).click();
  await expect(page.getByText("請輸入借閱人，才能完成借出。", { exact: true })).toBeVisible();

  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill("小美");
  const expectedDefaultDueDate = addDays(new Date(), 14);
  await expect(page.getByRole("textbox", { name: /預計歸還日期/ })).toHaveValue(expectedDefaultDueDate);
  await page.getByRole("button", { name: "清除日期" }).click();
  await expect(page.getByRole("textbox", { name: /預計歸還日期/ })).toHaveValue("");
  await page.getByLabel("借出備註", { exact: true }).fill("下星期還");
  await page.getByRole("button", { name: "確認借出" }).click();

  await expect(page.getByRole("heading", { name: "借閱狀態" })).toBeVisible();
  const currentBorrowingDetails = page.locator(".borrowing-details");
  await expect(currentBorrowingDetails.getByText("借閱人")).toBeVisible();
  await expect(currentBorrowingDetails.getByText("小美", { exact: true })).toBeVisible();
  await expect(currentBorrowingDetails.getByText("借出備註")).toBeVisible();
  await expect(currentBorrowingDetails.getByText("下星期還", { exact: true })).toBeVisible();
  await expect(currentBorrowingDetails.getByText("未設定", { exact: true })).toBeVisible();
  await expect(currentBorrowingDetails.getByText("借出日期")).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "借閱狀態" })).toBeVisible();
  await expect(page.locator(".borrowing-details").getByText("小美", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "已歸還" }).click();
  await expect(page.getByRole("heading", { name: "借閱狀態" })).toBeVisible();
  await expect(page.getByText("目前沒有借閱中的資料", { exact: true })).toBeVisible();
});

test("untouched visible default due date delegates to the backend clock", async ({ page }) => {
  await useFixedClock(page);
  const title = uniqueTitle("借閱預設日期測試");
  await addBook(page, title);

  await page.getByRole("button", { name: "借出", exact: true }).click();
  await expect(page.getByRole("textbox", { name: /預計歸還日期/ })).toHaveValue("2026-10-04");
  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill("預設日期借閱人");

  const borrowRequest = page.waitForRequest((request) =>
    request.method() === "POST" && request.url().endsWith("/borrow"));
  await page.getByRole("button", { name: "確認借出", exact: true }).click();
  const payload = JSON.parse((await borrowRequest).postData() ?? "{}");
  expect(payload.dueDate).toBeNull();
  expect(payload.clearDueDate).toBe(false);
  await expect(page.locator(".borrowing-details").getByText("預設日期借閱人", { exact: true })).toBeVisible();
});

test("borrow and return API reject invalid state transitions and preserve dates", async ({ page }) => {
  const title = uniqueTitle("借閱 API 測試");
  const createResponse = await page.request.post("/api/books", {
    data: { title },
  });
  expect(createResponse.ok()).toBeTruthy();
  const book = await createResponse.json();

  const missingBorrowerResponse = await page.request.post(`/api/books/${book.id}/borrow`, {
    data: { borrowerName: "", dueDate: null, note: "", clearDueDate: false },
  });
  expect(missingBorrowerResponse.status()).toBe(400);
  const missingBorrowerBody = await missingBorrowerResponse.json();
  expect(missingBorrowerBody.message).toBe("請輸入借閱人，才能完成借出。");

  const borrowResponse = await page.request.post(`/api/books/${book.id}/borrow`, {
    data: { borrowerName: "小王", dueDate: null, note: "兩週後歸還", clearDueDate: false },
  });
  expect(borrowResponse.ok()).toBeTruthy();
  const borrowedBook = await borrowResponse.json();
  expect(borrowedBook.status).toBe("BORROWED");
  expect(borrowedBook.currentBorrowing.borrowerName).toBe("小王");
  expect(borrowedBook.currentBorrowing.borrowDateUtc).toBeTruthy();
  expect(borrowedBook.currentBorrowing.dueDate).toBe(
    addUtcDays(borrowedBook.currentBorrowing.borrowDateUtc, 14),
  );

  const duplicateBorrowResponse = await page.request.post(`/api/books/${book.id}/borrow`, {
    data: { borrowerName: "另一位借閱人", dueDate: null, note: "", clearDueDate: false },
  });
  expect(duplicateBorrowResponse.status()).toBe(409);

  const returnResponse = await page.request.post(`/api/books/${book.id}/return`);
  expect(returnResponse.ok()).toBeTruthy();
  const returnedBook = await returnResponse.json();
  expect(returnedBook.status).toBe("HOME");
  expect(returnedBook.currentBorrowing).toBeNull();

  const clearDueDateBorrowResponse = await page.request.post(`/api/books/${book.id}/borrow`, {
    data: { borrowerName: "小王", dueDate: null, note: "無期限", clearDueDate: true },
  });
  expect(clearDueDateBorrowResponse.ok()).toBeTruthy();
  const clearDueDateBook = await clearDueDateBorrowResponse.json();
  expect(clearDueDateBook.currentBorrowing.dueDate).toBeNull();

  await page.request.post(`/api/books/${book.id}/return`);

  const duplicateReturnResponse = await page.request.post(`/api/books/${book.id}/return`);
  expect(duplicateReturnResponse.status()).toBe(409);
});
