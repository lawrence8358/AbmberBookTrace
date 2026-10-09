import { expect, test, type Page } from "@playwright/test";

// 這個檔案測建立帳號、登入、登出本身，所以直接使用 @playwright/test 的 test（一開始是未登入）。
test.describe.configure({ mode: "serial" });

const ACCOUNT = "reader";
const PASSWORD = "bookshelf-pass";

test.beforeEach(async ({ page }) => {
  // 清掉所有帳號，回到「還沒有任何帳號」的狀態。
  expect((await page.request.post("/api/test/auth/reset")).status()).toBe(204);
});

function accountButton(page: Page) {
  return page.getByRole("button", { name: /^Amber 的私人書房，目前(已登入|未登入)$/ });
}

function addBookEntry(page: Page) {
  return page.getByRole("link", { name: /新增書籍|新增第一本書/ });
}

async function openAccountMenu(page: Page) {
  await accountButton(page).click();
  return page.getByRole("dialog", { name: "Amber 的私人書房" });
}

async function openLoginDialog(page: Page) {
  const menu = await openAccountMenu(page);
  await menu.getByRole("button", { name: "登入", exact: true }).click();
}

async function fillCreateAccount(page: Page, account = ACCOUNT, password = PASSWORD, confirm = password) {
  const dialog = page.getByRole("dialog", { name: "建立帳號", exact: true });
  await dialog.getByLabel("帳號").fill(account);
  await dialog.getByLabel(/^密碼/).fill(password);
  await dialog.getByLabel("再輸入一次密碼").fill(confirm);
  await dialog.getByRole("button", { name: "建立帳號並登入" }).click();
  return dialog;
}

async function signIn(page: Page, password = PASSWORD) {
  const dialog = page.getByRole("dialog", { name: "登入", exact: true });
  await dialog.getByLabel("帳號").fill(ACCOUNT);
  await dialog.getByLabel("密碼").fill(password);
  await dialog.getByRole("button", { name: "登入", exact: true }).click();
  return dialog;
}

/** 直接用 API 建立帳號，再登出：之後的畫面是「已有帳號、尚未登入」。 */
async function createAccountThenSignOut(page: Page) {
  expect((await page.request.post("/api/auth/setup", { data: { userName: ACCOUNT, password: PASSWORD } })).status()).toBe(200);
  expect((await page.request.post("/api/auth/logout")).status()).toBe(204);
}

async function changePassword(page: Page, current: string, next: string, confirm = next) {
  const dialog = page.getByRole("dialog", { name: "變更密碼", exact: true });
  await dialog.getByLabel("目前的密碼").fill(current);
  await dialog.getByLabel("新密碼", { exact: true }).fill(next);
  await dialog.getByLabel("再輸入一次新密碼").fill(confirm);
  await dialog.getByRole("button", { name: "變更密碼", exact: true }).click();
  return dialog;
}

test("未登入時只能瀏覽，頭像選單提供登入，寫入 API 也會被拒絕", async ({ page }) => {
  await page.goto("/books");
  await expect(page.getByRole("heading", { name: "我的書庫", level: 1 })).toBeVisible();
  await expect(addBookEntry(page)).toHaveCount(0);

  const menu = await openAccountMenu(page);
  await expect(menu.getByText("目前未登入")).toBeVisible();
  await expect(menu.getByRole("button", { name: "登入", exact: true })).toBeVisible();
  await expect(menu.getByRole("button", { name: "登出" })).toHaveCount(0);

  expect((await page.request.post("/api/books", { data: { title: "未登入新增" } })).status()).toBe(401);
  expect((await page.request.get("/api/books")).status()).toBe(200);
});

test("完全沒有帳號時，登入視窗會變成建立帳號，建立後直接登入", async ({ page }) => {
  await page.goto("/books");
  await openLoginDialog(page);
  const dialog = page.getByRole("dialog", { name: "建立帳號", exact: true });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("這個書房還沒有帳號")).toBeVisible();

  await fillCreateAccount(page, ACCOUNT, "123");
  await expect(dialog.getByRole("alert")).toHaveText("密碼至少需要 4 個字。");
  await fillCreateAccount(page, "bad:name", PASSWORD);
  await expect(dialog.getByRole("alert")).toHaveText("帳號不能包含冒號（:）。");
  await fillCreateAccount(page, ACCOUNT, PASSWORD, "another-password");
  await expect(dialog.getByRole("alert")).toHaveText("兩次輸入的密碼不一樣。");

  await fillCreateAccount(page);
  await expect(dialog).toHaveCount(0);
  await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");
  await expect(addBookEntry(page).first()).toBeVisible();

  await page.reload();
  await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");

  // 帳號建立之後，登入視窗就是一般的登入，不會再讓人建立帳號。
  await (await openAccountMenu(page)).getByRole("button", { name: "登出", exact: true }).click();
  await openLoginDialog(page);
  await expect(page.getByRole("dialog", { name: "登入", exact: true })).toBeVisible();
  await expect(page.getByRole("dialog", { name: "建立帳號", exact: true })).toHaveCount(0);
});

test("沒登入就開新增頁會先登入，登入後回到那一頁", async ({ page }) => {
  await createAccountThenSignOut(page);
  await page.goto("/books/new");
  await expect(page).toHaveURL(/\/books$/);
  const login = page.getByRole("dialog", { name: "登入", exact: true });
  await expect(login).toBeVisible();

  await signIn(page);
  await expect(page).toHaveURL(/\/books\/new$/);
  await expect(page.getByLabel("書名（必填）", { exact: true })).toBeVisible();
});

test("沒有帳號時開新增頁，建立帳號後也會回到那一頁", async ({ page }) => {
  await page.goto("/books/new");
  await expect(page).toHaveURL(/\/books$/);
  await expect(page.getByRole("dialog", { name: "建立帳號", exact: true })).toBeVisible();

  await fillCreateAccount(page);
  await expect(page).toHaveURL(/\/books\/new$/);
  await expect(page.getByLabel("書名（必填）", { exact: true })).toBeVisible();
});

test("已有帳號時可以登入、登出，密碼錯誤會提示", async ({ page }) => {
  await createAccountThenSignOut(page);
  await page.goto("/books");
  await openLoginDialog(page);
  const login = await signIn(page, "wrong-password");
  await expect(login.getByRole("alert")).toHaveText("帳號或密碼不正確。");
  await expect(addBookEntry(page)).toHaveCount(0);

  await login.getByLabel("密碼").fill(PASSWORD);
  await login.getByRole("button", { name: "登入", exact: true }).click();
  await expect(login).toHaveCount(0);
  await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");
  await expect(addBookEntry(page).first()).toBeVisible();

  const menu = await openAccountMenu(page);
  await expect(menu.getByText("已登入")).toBeVisible();
  await expect(menu.getByRole("button", { name: "登入", exact: true })).toHaveCount(0);
  await menu.getByRole("button", { name: "登出", exact: true }).click();

  await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前未登入");
  await expect(addBookEntry(page)).toHaveCount(0);
  expect((await page.request.post("/api/books", { data: { title: "登出後新增" } })).status()).toBe(401);
});

test("登入後可以從頭像選單變更密碼", async ({ page }) => {
  await createAccountThenSignOut(page);
  await page.goto("/books");
  await openLoginDialog(page);
  await signIn(page);

  await (await openAccountMenu(page)).getByRole("button", { name: "變更密碼", exact: true }).click();
  const change = page.getByRole("dialog", { name: "變更密碼", exact: true });
  await changePassword(page, "wrong-current", "next-password");
  await expect(change.getByRole("alert")).toHaveText("目前的密碼不正確。");
  await changePassword(page, PASSWORD, "123");
  await expect(change.getByRole("alert")).toHaveText("新密碼至少需要 4 個字。");
  await changePassword(page, PASSWORD, PASSWORD);
  await expect(change.getByRole("alert")).toHaveText("新密碼不能和目前的密碼相同。");
  await changePassword(page, PASSWORD, "next-password", "different-password");
  await expect(change.getByRole("alert")).toHaveText("兩次輸入的新密碼不一樣。");

  await changePassword(page, PASSWORD, "next-password");
  await expect(change.getByRole("status")).toHaveText("密碼已經更新，下次登入請使用新密碼。");
  await change.getByRole("button", { name: "關閉" }).click();
  await expect(change).toHaveCount(0);

  await (await openAccountMenu(page)).getByRole("button", { name: "登出", exact: true }).click();
  await openLoginDialog(page);
  const login = await signIn(page, PASSWORD);
  await expect(login.getByRole("alert")).toHaveText("帳號或密碼不正確。");
  await login.getByLabel("密碼").fill("next-password");
  await login.getByRole("button", { name: "登入", exact: true }).click();
  await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");
});

test.describe("閒置超過 1 小時", () => {
  test.beforeEach(async ({ page }) => {
    expect((await page.request.post("/api/test/auth/sign-in")).status()).toBe(204);
    await page.clock.install();
  });

  test("沒有任何點擊或換頁就安靜地登出，期間有操作則重新計時", async ({ page }) => {
    await page.goto("/books");
    await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");

    await page.clock.runFor("59:00");
    await page.keyboard.press("Shift");
    await page.clock.runFor("59:00");
    await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");
    await expect(addBookEntry(page).first()).toBeVisible();

    await page.clock.runFor("02:00");
    await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前未登入");
    await expect(addBookEntry(page)).toHaveCount(0);
    await expect(page.locator("dialog[open]")).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    expect(await (await page.request.get("/api/auth/session")).json()).toMatchObject({ authenticated: false });
  });

  test("只有換頁、沒有點擊或按鍵，也算在使用", async ({ page }) => {
    await page.goto("/books");
    await page.getByRole("link", { name: /歷史$/ }).first().click();
    await expect(page).toHaveURL(/\/borrowings$/);

    await page.clock.runFor("59:00");
    await page.goBack();
    await expect(page).toHaveURL(/\/books$/);
    await page.clock.runFor("59:00");
    await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前已登入");
  });

  test("停在新增書籍頁時閒置登出，會回到書庫", async ({ page }) => {
    await page.goto("/books/new");
    await expect(page.getByLabel("書名（必填）", { exact: true })).toBeVisible();

    await page.clock.runFor("01:01:00");
    await expect(page).toHaveURL(/\/books$/);
    await expect(accountButton(page)).toHaveAccessibleName("Amber 的私人書房，目前未登入");
  });
});
