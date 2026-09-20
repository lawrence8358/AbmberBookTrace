import { expect, type Page } from "@playwright/test";

export const FIXED_NOW = "2026-09-20T09:00:00.000Z";

export function uniqueTitle(prefix: string) {
  return `${prefix} ${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export async function useFixedClock(page: Page, fixedNow = FIXED_NOW) {
  await page.addInitScript(`
    (() => {
      const fixedNow = ${JSON.stringify(fixedNow)};
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

export async function addBook(
  page: Page,
  title: string,
  fields: {
    author?: string;
    isbn?: string;
    location?: string;
    detailedLocation?: string;
  } = {},
) {
  await page.goto("/books/new");
  await page.getByLabel("書名（必填）", { exact: true }).fill(title);
  if (fields.author) {
    await page.getByLabel("作者", { exact: true }).fill(fields.author);
  }
  if (fields.isbn) {
    await page.getByLabel("ISBN", { exact: true }).fill(fields.isbn);
  }
  if (fields.location) {
    await page.getByLabel("位置", { exact: true }).fill(fields.location);
  }
  if (fields.detailedLocation) {
    await page.getByLabel("詳細位置", { exact: true }).fill(fields.detailedLocation);
  }
  await page.getByRole("button", { name: "儲存書籍", exact: true }).click();
  await expect(page).toHaveURL(/\/books\/\d+$/);
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible();
}

export async function expectNoHorizontalOverflow(page: Page) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
}
