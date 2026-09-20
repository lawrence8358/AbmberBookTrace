<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import {
  getBooks,
  getLibraryStats,
  getReminders,
  type Book,
  type BookStatusFilter,
  type BorrowingReminder,
  type LibraryStats,
} from "../api";
import ReminderList from "../components/ReminderList.vue";
import StatusBadge from "../components/StatusBadge.vue";

const books = ref<Book[]>([]);
const stats = ref<LibraryStats | null>(null);
const search = ref("");
const selectedStatus = ref<BookStatusFilter>("ALL");
const isLoading = ref(true);
const isStatsLoading = ref(true);
const errorMessage = ref("");
const statsErrorMessage = ref("");
const reminders = ref<BorrowingReminder[]>([]);
const isRemindersLoading = ref(true);
const remindersErrorMessage = ref("");
let latestBooksRequest = 0;

const statusFilters: Array<{ value: BookStatusFilter; label: string }> = [
  { value: "ALL", label: "全部" },
  { value: "HOME", label: "在家" },
  { value: "BORROWED", label: "借出中" },
];

const hasActiveFilter = computed(() => Boolean(search.value.trim()) || selectedStatus.value !== "ALL");

async function loadBooks() {
  const requestId = ++latestBooksRequest;
  isLoading.value = true;
  errorMessage.value = "";

  try {
    const loadedBooks = await getBooks({
      search: search.value,
      status: selectedStatus.value,
    });

    if (requestId === latestBooksRequest) {
      books.value = loadedBooks;
    }
  } catch (error) {
    if (requestId === latestBooksRequest) {
      errorMessage.value = error instanceof Error
        ? error.message
        : "目前無法載入書庫，請稍後再試。";
    }
  } finally {
    if (requestId === latestBooksRequest) {
      isLoading.value = false;
    }
  }
}

async function loadStats() {
  isStatsLoading.value = true;
  statsErrorMessage.value = "";

  try {
    stats.value = await getLibraryStats();
  } catch (error) {
    statsErrorMessage.value = error instanceof Error
      ? error.message
      : "目前無法載入書庫統計，請稍後再試。";
  } finally {
    isStatsLoading.value = false;
  }
}

async function loadReminders() {
  isRemindersLoading.value = true;
  remindersErrorMessage.value = "";

  try {
    reminders.value = await getReminders();
  } catch (error) {
    remindersErrorMessage.value = error instanceof Error
      ? error.message
      : "目前無法載入借閱提醒，請稍後再試。";
  } finally {
    isRemindersLoading.value = false;
  }
}

function clearFilters() {
  search.value = "";
  selectedStatus.value = "ALL";
}

watch([search, selectedStatus], () => {
  void loadBooks();
});

onMounted(() => {
  void loadBooks();
  void loadStats();
  void loadReminders();
});
</script>

<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">我的私人書房</p>
      <h1>我的書庫</h1>
      <p class="intro">搜尋書名、作者或 ISBN，快速找到每一本書。</p>
    </div>
    <RouterLink class="button button-primary" to="/books/new">＋ 新增書籍</RouterLink>
  </section>

  <section class="library-tools" aria-label="書庫搜尋與篩選">
    <label class="search-field">
      <span class="search-icon" aria-hidden="true">⌕</span>
      <span class="sr-only">搜尋書名、作者或 ISBN</span>
      <input
        v-model="search"
        type="search"
        placeholder="搜尋書名、作者、ISBN..."
        aria-label="搜尋書名、作者或 ISBN"
      />
      <button v-if="search" class="search-clear" type="button" aria-label="清除搜尋" @click="search = ''">×</button>
    </label>

    <div class="filter-pills" role="group" aria-label="書籍狀態篩選">
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
  </section>

  <p v-if="statsErrorMessage" class="feedback feedback-error" role="alert">{{ statsErrorMessage }}</p>
  <section v-else class="stats-grid" aria-label="書庫統計">
    <article class="stat-card">
      <span class="stat-icon" aria-hidden="true">📚</span>
      <div>
        <p>藏書總數</p>
        <strong v-if="!isStatsLoading">{{ stats?.totalCount ?? 0 }}</strong>
        <strong v-else aria-label="統計載入中">…</strong>
      </div>
    </article>
    <article class="stat-card">
      <span class="stat-icon" aria-hidden="true">🏠</span>
      <div>
        <p>在家</p>
        <strong v-if="!isStatsLoading">{{ stats?.homeCount ?? 0 }}</strong>
        <strong v-else aria-label="統計載入中">…</strong>
      </div>
    </article>
    <article class="stat-card">
      <span class="stat-icon" aria-hidden="true">👤</span>
      <div>
        <p>借出中</p>
        <strong v-if="!isStatsLoading">{{ stats?.borrowedCount ?? 0 }}</strong>
        <strong v-else aria-label="統計載入中">…</strong>
      </div>
    </article>
  </section>

  <p v-if="remindersErrorMessage" class="feedback feedback-error" role="alert">{{ remindersErrorMessage }}</p>
  <section
    v-else-if="!isRemindersLoading && reminders.length"
    class="reminders-summary"
    aria-labelledby="reminders-summary-title"
  >
    <div class="section-heading-row">
      <div>
        <p class="eyebrow">借閱狀態</p>
        <h2 id="reminders-summary-title">借閱提醒</h2>
      </div>
      <RouterLink class="text-link" to="/notifications">查看全部提醒 →</RouterLink>
    </div>
    <ReminderList :reminders="reminders" />
  </section>

  <section v-if="!isStatsLoading && stats?.recentBooks.length" class="recent-section" aria-labelledby="recent-books-title">
    <div class="section-heading-row">
      <div>
        <p class="eyebrow">剛放進書房</p>
        <h2 id="recent-books-title">最近新增</h2>
      </div>
      <span class="section-note">最新 4 本</span>
    </div>
    <div class="recent-book-list">
      <article v-for="book in stats.recentBooks" :key="book.id" class="recent-book-card">
        <div>
          <p class="book-card-label">BOOK {{ String(book.id).padStart(2, "0") }}</p>
          <h3><RouterLink :to="`/books/${book.id}`">{{ book.title }}</RouterLink></h3>
          <p class="book-author">{{ book.author || "未記錄作者" }}</p>
        </div>
        <StatusBadge :status="book.status" />
      </article>
    </div>
  </section>

  <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
  <div v-else-if="isLoading" class="loading-state" role="status">正在整理你的書庫⋯</div>

  <section v-else-if="books.length === 0" class="empty-state" aria-labelledby="empty-library-title">
    <div class="empty-illustration" aria-hidden="true">📚</div>
    <h2 id="empty-library-title">{{ hasActiveFilter ? "找不到符合的書籍" : "目前還沒有藏書" }}</h2>
    <p v-if="hasActiveFilter">試試其他書名、作者、ISBN 或狀態篩選。</p>
    <p v-else>先登錄一本書，之後就能隨時找到它的位置。</p>
    <button v-if="hasActiveFilter" class="button button-secondary" type="button" @click="clearFilters">清除搜尋與篩選</button>
    <RouterLink v-else class="button button-primary" to="/books/new">新增第一本書</RouterLink>
  </section>

  <section v-else class="library-results" aria-labelledby="library-results-title">
    <div class="section-heading-row">
      <div>
        <p class="eyebrow">書房清單</p>
        <h2 id="library-results-title">全部藏書</h2>
      </div>
      <span class="section-note">{{ books.length }} 本</span>
    </div>
    <div class="book-grid" aria-label="書籍列表">
      <article v-for="book in books" :key="book.id" class="book-card">
        <div class="book-card-cover">
          <img v-if="book.coverUrl" :src="book.coverUrl" :alt="`${book.title} 的封面`" />
          <span v-else aria-hidden="true">封面</span>
        </div>
        <div class="book-card-main">
          <p class="book-card-label">BOOK {{ String(book.id).padStart(2, "0") }}</p>
          <h3><RouterLink :to="`/books/${book.id}`">{{ book.title }}</RouterLink></h3>
          <p class="book-author">{{ book.author || "未記錄作者" }}</p>
          <p class="book-location">
            <span aria-hidden="true">⌖</span>
            {{ book.location || "尚未記錄位置" }}<template v-if="book.detailedLocation"> · {{ book.detailedLocation }}</template>
          </p>
        </div>
        <StatusBadge :status="book.status" />
      </article>
    </div>
  </section>
</template>
