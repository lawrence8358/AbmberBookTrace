import { expect, test, type Page } from "@playwright/test";

test.describe.configure({ mode: "serial" });

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
  await expect(page.locator(".library-results").getByRole("link", { name: "夜航西飛" })).toBeVisible();
});

async function addBook(
  page: Page,
  book: { title: string; author?: string; isbn?: string },
) {
  await page.getByRole("link", { name: "新增書籍", exact: true }).click();
  await page.getByLabel("書名（必填）", { exact: true }).fill(book.title);
  if (book.author) {
    await page.getByLabel("作者", { exact: true }).fill(book.author);
  }
  if (book.isbn) {
    await page.getByLabel("ISBN", { exact: true }).fill(book.isbn);
  }
  await page.getByRole("button", { name: "儲存書籍" }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  await expect(page.getByRole("heading", { name: book.title, exact: true })).toBeVisible();
  await page.goto("/books");
}

test("user can search, filter, sort, and review library statistics", async ({ page }) => {
  await page.goto("/books");

  const stats = page.getByRole("region", { name: "書庫統計" });
  const totalCount = stats.locator(".stat-card").nth(0).locator("strong");
  await expect(totalCount).toHaveText(/^\d+$/);
  const initialTotal = Number(await totalCount.textContent());

  const books = [
    { title: "Shared Beta", author: "Shared Author", isbn: "ISBN-02" },
    { title: "Shared Alpha", author: "Shared Author", isbn: "ISBN-01" },
    { title: "Solo Title", author: "Solo Author", isbn: "ISBN-03" },
    { title: "Untitled Shelf", isbn: "ISBN-04" },
    { title: "Newest Entry", author: "Newest Author", isbn: "ISBN-05" },
  ];

  for (const book of books) {
    await addBook(page, book);
  }

  await expect(page.getByText("藏書總數")).toBeVisible();
  await expect(stats.getByText("在家", { exact: true })).toBeVisible();
  await expect(stats.getByText("借出中", { exact: true })).toBeVisible();
  const expectedTotal = String(initialTotal + books.length);
  await expect(totalCount).toHaveText(expectedTotal);
  await expect(page.locator(".stat-card").nth(1).locator("strong")).toHaveText(expectedTotal);
  await expect(page.locator(".stat-card").nth(2).locator("strong")).toHaveText("0");

  const recentBooks = page.locator(".recent-book-list .recent-book-card");
  await expect(recentBooks).toHaveCount(4);
  await expect(recentBooks.nth(0).getByRole("link", { name: "Newest Entry", exact: true })).toBeVisible();
  await expect(recentBooks.nth(3).getByRole("link", { name: "Shared Alpha", exact: true })).toBeVisible();

  const searchInput = page.getByRole("searchbox", { name: "搜尋書名、作者或 ISBN" });
  const results = page.locator(".library-results .book-card");

  await searchInput.fill("  sHaReD beTa ");
  await expect(results).toHaveCount(1);
  await expect(results.getByRole("link", { name: "Shared Beta", exact: true })).toBeVisible();

  await searchInput.fill("shared author");
  await expect(results).toHaveCount(2);

  await searchInput.fill("isbn-03");
  await expect(results).toHaveCount(1);
  await expect(results.getByRole("link", { name: "Solo Title", exact: true })).toBeVisible();

  await searchInput.fill("");
  await page.getByRole("button", { name: "在家", exact: true }).click();
  await expect(results).toHaveCount(Number(expectedTotal));

  await page.getByRole("button", { name: "借出中", exact: true }).click();
  await expect(page.getByRole("heading", { name: "找不到符合的書籍" })).toBeVisible();
  await expect(totalCount).toHaveText(expectedTotal);
  await expect(page.locator(".stat-card").nth(1).locator("strong")).toHaveText(expectedTotal);
  await expect(page.locator(".stat-card").nth(2).locator("strong")).toHaveText("0");

  await searchInput.fill("shared");
  await expect(page.getByRole("heading", { name: "找不到符合的書籍" })).toBeVisible();
  await page.getByRole("button", { name: "在家", exact: true }).click();
  await expect(results).toHaveCount(2);

  await page.getByRole("button", { name: "全部", exact: true }).click();
  await searchInput.fill("");
  await expect(results).toHaveCount(Number(expectedTotal));

  const resultTitles = await results.locator("h3 a").allTextContents();
  expect(resultTitles.slice(0, 2)).toEqual(["Shared Alpha", "Shared Beta"]);
  expect(resultTitles.at(-1)).toBe("Untitled Shelf");

  await searchInput.fill("no-such-book-9f1a");
  await expect(page.getByRole("heading", { name: "找不到符合的書籍" })).toBeVisible();
  await expect(page.getByText("試試其他書名、作者、ISBN 或狀態篩選。")).toBeVisible();
});
