import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import BookDetailPage from "./pages/BookDetailPage.vue";
import BookFormPage from "./pages/BookFormPage.vue";
import LibraryPage from "./pages/LibraryPage.vue";
import "./style.css";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/books" },
    { path: "/books", component: LibraryPage },
    { path: "/books/new", component: BookFormPage },
    { path: "/books/:id", component: BookDetailPage },
  ],
});

createApp(App).use(router).mount("#app");
