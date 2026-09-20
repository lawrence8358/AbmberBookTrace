<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { getBooks, type Book } from "../api";
import StatusBadge from "../components/StatusBadge.vue";

const books = ref<Book[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");

async function loadBooks() {
  isLoading.value = true;
  errorMessage.value = "";

  try {
    books.value = await getBooks();
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : "目前無法載入書庫，請稍後再試。";
  } finally {
    isLoading.value = false;
  }
}

onMounted(loadBooks);
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">我的私人書房</p>
      <h1>我的書庫</h1>
      <p class="intro">把每一本書放回它熟悉的位置。</p>
    </div>
    <RouterLink class="button button-primary" to="/books/new">＋ 新增書籍</RouterLink>
  </section>

  <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
  <div v-else-if="isLoading" class="loading-state" role="status">正在整理你的書庫⋯</div>

  <section v-else-if="books.length === 0" class="empty-state" aria-labelledby="empty-library-title">
    <div class="empty-illustration" aria-hidden="true">📚</div>
    <h2 id="empty-library-title">目前還沒有藏書</h2>
    <p>先登錄一本書，之後就能隨時找到它的位置。</p>
    <RouterLink class="button button-primary" to="/books/new">新增第一本書</RouterLink>
  </section>

  <section v-else class="book-grid" aria-label="書籍列表">
    <article v-for="book in books" :key="book.id" class="book-card">
      <div class="book-card-main">
        <p class="book-card-label">BOOK {{ String(book.id).padStart(2, "0") }}</p>
        <h2><RouterLink :to="`/books/${book.id}`">{{ book.title }}</RouterLink></h2>
        <p class="book-author">{{ book.author || "未記錄作者" }}</p>
        <p class="book-location">
          <span aria-hidden="true">⌖</span>
          {{ book.location || "尚未記錄位置" }}<template v-if="book.detailedLocation"> · {{ book.detailedLocation }}</template>
        </p>
      </div>
      <StatusBadge :status="book.status" />
    </article>
  </section>
</template>
