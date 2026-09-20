<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import {
  getBorrowingHistory,
  type BorrowingHistoryFilter,
  type BorrowingHistoryRecord,
} from "../api";

const records = ref<BorrowingHistoryRecord[]>([]);
const selectedStatus = ref<BorrowingHistoryFilter>("ALL");
const isLoading = ref(true);
const errorMessage = ref("");

const statusFilters: Array<{ value: BorrowingHistoryFilter; label: string }> = [
  { value: "ALL", label: "全部紀錄" },
  { value: "CURRENT", label: "尚未歸還" },
  { value: "RETURNED", label: "已完成" },
];

function formatDate(value: string | null) {
  if (!value) {
    return "未設定";
  }

  const date = value.includes("T") ? new Date(value) : new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(date);
}

async function loadHistory() {
  isLoading.value = true;
  errorMessage.value = "";

  try {
    records.value = await getBorrowingHistory(selectedStatus.value);
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : "目前無法載入借閱歷史，請稍後再試。";
  } finally {
    isLoading.value = false;
  }
}

watch(selectedStatus, () => {
  void loadHistory();
});

onMounted(() => {
  void loadHistory();
});
</script>

<template>
  <section class="page-heading compact-heading">
    <div>
      <p class="eyebrow">書籍流轉紀錄</p>
      <h1>借閱歷史</h1>
      <p class="intro">每次借出與歸還都會保留，歷史紀錄只能查看，不能修改或刪除。</p>
    </div>
    <RouterLink class="button button-secondary" to="/notifications">查看提醒</RouterLink>
  </section>

  <div class="filter-pills history-filters" role="group" aria-label="借閱歷史篩選">
    <button
      v-for="filter in statusFilters"
      :key="filter.value"
      class="filter-pill"
      :class="{ 'filter-pill-active': selectedStatus === filter.value }"
      type="button"
      :aria-pressed="selectedStatus === filter.value"
      @click="selectedStatus = filter.value"
    >
      {{ filter.label }}
    </button>
  </div>

  <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
  <div v-else-if="isLoading" class="loading-state" role="status">正在整理借閱歷史⋯</div>

  <section v-else-if="records.length === 0" class="empty-state history-empty" aria-labelledby="empty-history-title">
    <div class="empty-illustration" aria-hidden="true">📝</div>
    <h2 id="empty-history-title">目前沒有借閱紀錄</h2>
    <p>借出一本書後，這裡會留下完整的流轉紀錄。</p>
    <RouterLink class="button button-primary" to="/books">回到書庫</RouterLink>
  </section>

  <section v-else class="history-results" aria-labelledby="history-results-title">
    <div class="section-heading-row">
      <div>
        <p class="eyebrow">只讀紀錄</p>
        <h2 id="history-results-title">借閱紀錄</h2>
      </div>
      <span class="section-note">{{ records.length }} 筆</span>
    </div>

    <div class="history-list">
      <article
        v-for="record in records"
        :key="record.id"
        class="history-card"
        :data-history-status="record.status"
      >
        <div class="history-card-heading">
          <div class="history-book-heading">
            <div class="history-cover" aria-hidden="true">
              <img v-if="record.coverUrl" :src="record.coverUrl" alt="" />
              <span v-else>書</span>
            </div>
            <div>
              <p class="book-card-label">借閱紀錄 #{{ record.id }}</p>
              <h3><RouterLink :to="`/books/${record.bookId}`">{{ record.bookTitle }}</RouterLink></h3>
              <p class="book-author">{{ record.bookAuthor || "未記錄作者" }}</p>
            </div>
          </div>
          <span
            class="history-status"
            :class="record.status === 'CURRENT' ? 'history-status-current' : 'history-status-returned'"
          >
            {{ record.status === "CURRENT" ? "目前借閱" : "已歸還" }}
          </span>
        </div>

        <dl class="metadata-list history-metadata">
          <div><dt>借閱人</dt><dd>{{ record.borrowerName }}</dd></div>
          <div><dt>借出日期</dt><dd>{{ formatDate(record.borrowDateUtc) }}</dd></div>
          <div><dt>預計歸還日期</dt><dd>{{ formatDate(record.dueDate) }}</dd></div>
          <div><dt>實際歸還日期</dt><dd>{{ formatDate(record.returnedAtUtc) }}</dd></div>
          <div v-if="record.note"><dt>借出備註</dt><dd>{{ record.note }}</dd></div>
        </dl>
      </article>
    </div>
  </section>
</template>
