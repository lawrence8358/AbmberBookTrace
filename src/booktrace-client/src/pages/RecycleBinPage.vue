<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { getRecycleBin, restoreBook, type RecycleBinBook } from "../api";
import StatusBadge from "../components/StatusBadge.vue";

const router = useRouter();
const books = ref<RecycleBinBook[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");
const restoringId = ref<number | null>(null);
const restoreError = ref("");

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(new Date(value));
}

function daysRemaining(book: RecycleBinBook) {
  const remaining = Math.ceil((new Date(book.expiresAtUtc).getTime() - Date.now()) / 86_400_000);
  return Math.max(0, remaining);
}

async function loadBooks() {
  isLoading.value = true;
  errorMessage.value = "";
  try {
    books.value = await getRecycleBin();
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : "目前無法載入資源回收筒，請稍後再試。";
  } finally {
    isLoading.value = false;
  }
}

async function restore(book: RecycleBinBook) {
  restoringId.value = book.id;
  restoreError.value = "";
  try {
    await restoreBook(book.id);
    await router.push(`/books/${book.id}`);
  } catch (error) {
    restoreError.value = error instanceof Error
      ? error.message
      : "目前無法還原書籍，請稍後再試。";
    restoringId.value = null;
    await loadBooks();
  }
}

onMounted(() => {
  void loadBooks();
});
</script>

<template>
  <section class="page-heading compact-heading">
    <div>
      <p class="eyebrow">保留完整資料</p>
      <h1>資源回收筒</h1>
      <p class="intro">刪除的書籍會保留 30 天，還原時封面與借閱歷史也會一起回來。</p>
    </div>
    <RouterLink class="button button-secondary" to="/books">回到我的書庫</RouterLink>
  </section>

  <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
  <div v-else-if="isLoading" class="loading-state" role="status">正在整理資源回收筒⋯</div>

  <section v-else-if="books.length" class="recycle-results" aria-labelledby="recycle-results-title">
    <div class="section-heading-row">
      <div>
        <p class="eyebrow">最近刪除</p>
        <h2 id="recycle-results-title">待還原書籍</h2>
      </div>
      <span class="section-note">{{ books.length }} 本</span>
    </div>

    <p v-if="restoreError" class="feedback feedback-error" role="alert">{{ restoreError }}</p>
    <div class="recycle-list">
      <article v-for="book in books" :key="book.id" class="recycle-card">
        <div class="recycle-cover">
          <img v-if="book.coverUrl" :src="book.coverUrl" :alt="`${book.title} 的封面`" />
          <span v-else aria-hidden="true">封面</span>
        </div>
        <div class="recycle-card-main">
          <p class="book-card-label">BOOK {{ String(book.id).padStart(2, "0") }}</p>
          <h3>{{ book.title }}</h3>
          <p class="book-author">{{ book.author || "未記錄作者" }}</p>
          <p class="recycle-meta">刪除於 {{ formatDate(book.deletedAtUtc) }} · {{ daysRemaining(book) }} 天內可還原</p>
        </div>
        <div class="recycle-card-actions">
          <StatusBadge :status="book.status" />
          <button
            class="button button-primary desktop-only"
            type="button"
            :disabled="restoringId === book.id"
            @click="restore(book)"
          >
            {{ restoringId === book.id ? "還原中⋯" : "還原書籍" }}
          </button>
        </div>
      </article>
    </div>
  </section>

  <section v-else class="empty-state recycle-empty" aria-labelledby="empty-recycle-title">
    <div class="empty-illustration" aria-hidden="true">🌿</div>
    <h2 id="empty-recycle-title">資源回收筒是空的</h2>
    <p>刪除書籍後，還可以在 30 天內從這裡還原。</p>
    <RouterLink class="button button-primary" to="/books">回到我的書庫</RouterLink>
  </section>
</template>
