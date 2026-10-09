import { computed, reactive } from "vue";
import * as api from "./api";

/** 預設與伺服器相同；實際值會用 /api/auth/session 回傳的設定覆蓋。 */
const DEFAULT_IDLE_TIMEOUT_MS = 60 * 60 * 1000;
const IDLE_CHECK_INTERVAL_MS = 15_000;
const KEEP_ALIVE_INTERVAL_MS = 5 * 60 * 1000;
const SESSION_REQUEST_TIMEOUT_MS = 4_000;
const ACTIVITY_EVENTS = ["pointerdown", "keydown"] as const;

export const auth = reactive({
  userName: null as string | null,
  setupRequired: false,
  idleTimeoutMs: DEFAULT_IDLE_TIMEOUT_MS,
  loginOpen: false,
  changePasswordOpen: false,
  /** 被擋下來的頁面，登入完成後會帶使用者過去。 */
  pendingRedirect: null as string | null,
});

export const isSignedIn = computed(() => auth.userName !== null);
/** 新增、修改、刪除、借出與歸還：要登入。 */
export const canEdit = computed(() => isSignedIn.value);
export const isChangePasswordOpen = computed(() => isSignedIn.value && auth.changePasswordOpen);

let lastActivityAt = Date.now();
let lastKeepAliveAt = Date.now();
let idleTimer: number | undefined;

function startIdleWatch() {
  lastActivityAt = lastKeepAliveAt = Date.now();
  if (idleTimer !== undefined) return;

  for (const type of ACTIVITY_EVENTS) window.addEventListener(type, noteActivity, { capture: true, passive: true });
  document.addEventListener("visibilitychange", expireIfIdle);
  idleTimer = window.setInterval(expireIfIdle, IDLE_CHECK_INTERVAL_MS);
}

function stopIdleWatch() {
  if (idleTimer === undefined) return;

  for (const type of ACTIVITY_EVENTS) window.removeEventListener(type, noteActivity, { capture: true });
  document.removeEventListener("visibilitychange", expireIfIdle);
  window.clearInterval(idleTimer);
  idleTimer = undefined;
}

function clearSession() {
  auth.userName = null;
  auth.changePasswordOpen = false;
  stopIdleWatch();
}

/** 超過閒置時間就安靜地登出（不提醒）。回傳 true 代表剛剛登出了。 */
function expireIfIdle(): boolean {
  if (!isSignedIn.value || Date.now() - lastActivityAt < auth.idleTimeoutMs) return false;

  void api.logout().catch(() => undefined);
  clearSession();
  return true;
}

/** 點擊、按鍵與換頁都算「有在使用」。閒置過久後的第一下操作不能讓登入復活。 */
export function noteActivity() {
  if (!isSignedIn.value || expireIfIdle()) return;

  const now = Date.now();
  lastActivityAt = now;
  // 只在頁面上操作、沒有呼叫 API 的時候，伺服器也要知道使用者還在，登入才不會被伺服器先收回。
  if (now - lastKeepAliveAt >= KEEP_ALIVE_INTERVAL_MS) {
    lastKeepAliveAt = now;
    void api.getSession().then((session) => {
      if (!session.authenticated) clearSession();
    }).catch(() => undefined);
  }
}

function applySession(session: api.AuthSession) {
  auth.idleTimeoutMs = session.idleTimeoutSeconds * 1000;
  auth.setupRequired = session.setupRequired;
  if (!session.authenticated) {
    clearSession();
    return;
  }

  auth.userName = session.userName;
  startIdleWatch();
}

export async function initAuth() {
  api.onUnauthorized(clearSession);
  try {
    applySession(await api.getSession({ timeoutMs: SESSION_REQUEST_TIMEOUT_MS }));
  } catch {
    clearSession();
  }
}

export async function signIn(userName: string, password: string) {
  applySession(await api.login(userName, password));
  auth.loginOpen = false;
}

/** 還沒有任何帳號時，建立第一個帳號並直接登入。 */
export async function createAccount(userName: string, password: string) {
  try {
    applySession(await api.setupAccount(userName, password));
  } catch (error) {
    // 失敗時重新確認一次：如果是別人剛好先建立了帳號，就改回一般的登入畫面。
    void api.getSession().then((session) => {
      if (!session.authenticated) auth.setupRequired = session.setupRequired;
    }).catch(() => undefined);
    throw error;
  }
  auth.loginOpen = false;
}

export async function signOut() {
  try {
    await api.logout();
  } catch {
    // 連不上伺服器時仍然收起這個畫面的登入狀態，登入憑證會在閒置時限後自己失效。
  }
  auth.pendingRedirect = null;
  clearSession();
}

export async function changePassword(currentPassword: string, newPassword: string) {
  applySession(await api.changePassword(currentPassword, newPassword));
}

export function requestLogin(redirectTo: string | null = null) {
  auth.pendingRedirect = redirectTo;
  if (!isSignedIn.value) auth.loginOpen = true;
}

export function closeLogin() {
  auth.loginOpen = false;
  auth.pendingRedirect = null;
}

export function openChangePassword() {
  auth.changePasswordOpen = true;
}

export function closeChangePassword() {
  auth.changePasswordOpen = false;
}

export function takePendingRedirect(): string | null {
  const target = auth.pendingRedirect;
  auth.pendingRedirect = null;
  return target;
}
