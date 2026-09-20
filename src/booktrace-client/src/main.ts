import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import BookDetailPage from "./pages/BookDetailPage.vue";
import BookFormPage from "./pages/BookFormPage.vue";
import LibraryPage from "./pages/LibraryPage.vue";
import BorrowingHistoryPage from "./pages/BorrowingHistoryPage.vue";
import NotificationsPage from "./pages/NotificationsPage.vue";
import RecycleBinPage from "./pages/RecycleBinPage.vue";
import "./style.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/books" },
    { path: "/books", component: LibraryPage },
    { path: "/borrowings", component: BorrowingHistoryPage },
    { path: "/notifications", component: NotificationsPage },
    { path: "/recycle-bin", component: RecycleBinPage },
    { path: "/books/new", component: BookFormPage },
    { path: "/books/:id/edit", component: BookFormPage },
    { path: "/books/:id", component: BookDetailPage },
  ],
});

createApp(App).use(router).mount("#app");
