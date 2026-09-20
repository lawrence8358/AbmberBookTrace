<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { getBook, type Book } from "../api";

const route = useRoute();
const book = ref<Book | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");

onMounted(async () => {
  try {
    book.value = await getBook(String(route.params.id));
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : "找不到這本書。";
  } finally {
    isLoading.value = false;
  }
});
</script>

<template>
  <section v-if="isLoading" class="loading-state" role="status">正在打開書籍資料⋯</section>
  <p v-else-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
  <section v-else-if="book" class="detail-page">
    <RouterLink class="back-link" to="/books">← 回到我的書庫</RouterLink>

    <div class="detail-header">
      <div>
        <p class="eyebrow">書籍詳細資料</p>
        <h1>{{ book.title }}</h1>
        <p class="detail-author">{{ book.author || "未記錄作者" }}</p>
      </div>
      <span class="status-badge status-home"><span aria-hidden="true">●</span> 在家</span>
    </div>

    <div class="detail-grid">
      <section class="detail-card location-card">
        <p class="detail-label">目前位置</p>
        <p class="detail-value location-value">{{ book.location || "尚未記錄位置" }}</p>
        <p v-if="book.detailedLocation" class="detail-subvalue">{{ book.detailedLocation }}</p>
      </section>
      <section class="detail-card">
        <p class="detail-label">書籍資訊</p>
        <dl class="metadata-list">
          <div><dt>ISBN</dt><dd>{{ book.isbn || "未記錄" }}</dd></div>
          <div><dt>出版社</dt><dd>{{ book.publisher || "未記錄" }}</dd></div>
          <div><dt>分類／標籤</dt><dd>{{ book.category || "未記錄" }}</dd></div>
        </dl>
      </section>
    </div>

    <section v-if="book.notes" class="detail-card notes-card">
      <p class="detail-label">備註</p>
      <p class="notes-value">{{ book.notes }}</p>
    </section>
  </section>
</template>
