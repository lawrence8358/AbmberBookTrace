import { expect, test } from "./helpers";

for (const width of [1440, 390]) {
  test.describe(`shared header at ${width}px`, () => {
    test.use({ viewport: { width, height: 800 } });

    test("keeps tab page titles at one vertical position", async ({ page }) => {
      const tops: number[] = [];
      for (const route of ["/books", "/borrowings", "/books/new", "/notifications", "/recycle-bin", "/settings"]) {
        await page.goto(route);
        const title = page.getByRole("heading", { level: 1 });
        await expect(title).toBeVisible();
        tops.push((await title.boundingBox())!.y);
      }
      expect(Math.max(...tops) - Math.min(...tops)).toBeLessThan(1);
    });

    test("retries a failed reminder request and returns focus after Escape", async ({ page }) => {
      let requests = 0;
      await page.route("**/api/reminders", async route => {
        requests++;
        await route.fulfill({
          status: requests === 1 ? 503 : 200,
          contentType: "application/json",
          body: requests === 1 ? JSON.stringify({ message: "提醒暫時無法載入" }) : "[]",
        });
      });
      await page.goto("/books");
      const bell = page.getByRole("button", { name: "查看提醒", exact: true });
      await bell.click();
      const panel = page.getByRole("dialog", { name: "書房提醒" });
      await expect(panel.getByRole("alert")).toHaveText("提醒暫時無法載入");
      await panel.getByRole("button", { name: "重新載入" }).click();
      await expect(panel.getByRole("heading", { name: "目前沒有需要處理的提醒" })).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(panel).not.toBeVisible();
      await expect(bell).toBeFocused();
      await bell.click();
      await expect(panel.getByRole("heading", { name: "目前沒有需要處理的提醒" })).toBeVisible();
      await expect.poll(() => requests).toBe(3);
    });
  });
}
