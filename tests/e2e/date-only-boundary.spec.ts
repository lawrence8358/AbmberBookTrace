import { expect, test } from "@playwright/test";
import { addBook, uniqueTitle, useFixedClock } from "./helpers";

const BOUNDARY_NOW = "2026-09-19T23:30:00.000Z";
const LOCAL_TODAY = "2026-09-20";
const DEFAULT_DUE_DATE = "2026-10-04";

test("uses the local borrow date for default due dates and reminders before 08:00 UTC", async ({ page }) => {
  await useFixedClock(page, BOUNDARY_NOW);
  const defaultDueTitle = uniqueTitle("本地日期預設期限測試");
  await addBook(page, defaultDueTitle);

  await page.getByRole("button", { name: "借出", exact: true }).click();
  await expect(page.getByRole("textbox", { name: /預計歸還日期/ })).toHaveValue(DEFAULT_DUE_DATE);
  await page.getByRole("textbox", { name: /借閱人（必填）/ }).fill("本地日期借閱人");
  await page.getByRole("button", { name: "確認借出", exact: true }).click();
  await expect(page.locator(".borrowing-details").getByText("本地日期借閱人", { exact: true })).toBeVisible();

  const defaultDueBook = await page.request.get(`/api/books/${new URL(page.url()).pathname.split("/").pop()}`);
  const defaultDueBookBody = await defaultDueBook.json();
  expect(defaultDueBookBody.currentBorrowing.dueDate).toBe(DEFAULT_DUE_DATE);

  const reminderTitle = uniqueTitle("本地日期提醒測試");
  const createResponse = await page.request.post("/api/books", { data: { title: reminderTitle } });
  expect(createResponse.ok()).toBeTruthy();
  const reminderBook = await createResponse.json();
  const reminderBorrowResponse = await page.request.post(`/api/books/${reminderBook.id}/borrow`, {
    data: {
      borrowerName: "本地日期提醒借閱人",
      dueDate: LOCAL_TODAY,
      note: "今天到期",
      clearDueDate: false,
    },
  });
  expect(reminderBorrowResponse.ok()).toBeTruthy();

  const remindersResponse = await page.request.get("/api/reminders");
  expect(remindersResponse.ok()).toBeTruthy();
  const reminders = await remindersResponse.json();
  expect(reminders).toEqual(expect.arrayContaining([
    expect.objectContaining({
      bookId: reminderBook.id,
      dueDate: LOCAL_TODAY,
      reminderType: "DUE_TODAY",
    }),
  ]));
});
