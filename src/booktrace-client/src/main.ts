import { createApp, watch } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import BookDetailPage from "./pages/BookDetailPage.vue";
import BookFormPage from "./pages/BookFormPage.vue";
import LibraryPage from "./pages/LibraryPage.vue";
import BorrowingHistoryPage from "./pages/BorrowingHistoryPage.vue";
import NotificationsPage from "./pages/NotificationsPage.vue";
import RecycleBinPage from "./pages/RecycleBinPage.vue";
import SettingsPage from "./pages/SettingsPage.vue";
import { canEdit, initAuth, noteActivity, requestLogin, takePendingRedirect } from "./auth";
import { initializeReadingPreferences } from "./readingPreferences";
import "./style.css";

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to) {
    if (to.hash) {
      return { el: to.hash, behavior: "smooth" };
    }

    return { top: 0 };
  },
  routes: [
    { path: "/", redirect: "/books" },
    { path: "/books", component: LibraryPage },
    { path: "/borrowings", component: BorrowingHistoryPage },
    { path: "/notifications", component: NotificationsPage },
    { path: "/recycle-bin", component: RecycleBinPage },
    { path: "/settings", component: SettingsPage },
    { path: "/books/new", component: BookFormPage, meta: { requiresAuth: true } },
    { path: "/books/:id/edit", component: BookFormPage, meta: { requiresAuth: true } },
    { path: "/books/:id", component: BookDetailPage },
  ],
});

// 新增與修改頁要登入才能進入：沒登入就跳出登入視窗，登入後再帶使用者過去。
router.beforeEach((to, from) => {
  if (!to.meta.requiresAuth || canEdit.value) return true;

  requestLogin(to.fullPath);
  return from.matched.length ? false : "/books";
});
router.afterEach(() => noteActivity());

watch(canEdit, (allowed) => {
  if (allowed) {
    const target = takePendingRedirect();
    if (target) void router.push(target);
  } else if (router.currentRoute.value.meta.requiresAuth) {
    void router.replace("/books");
  }
});

initializeReadingPreferences();
void initAuth().then(() => createApp(App).use(router).mount("#app"));
