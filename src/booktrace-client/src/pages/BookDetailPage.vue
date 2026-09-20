<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import {
  borrowBook,
  deleteBook,
  getBook,
  getBookBorrowingHistory,
  removeBookCover,
  returnBook,
  type BorrowingHistoryRecord,
  type Book,
  uploadBookCover,
} from "../api";
import BookCoverPicker from "../components/BookCoverPicker.vue";
import StatusBadge from "../components/StatusBadge.vue";

const route = useRoute();
const router = useRouter();
const book = ref<Book | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");
const borrowError = ref("");
const borrowerError = ref("");
const isBorrowFormOpen = ref(false);
const isSavingBorrow = ref(false);
const isReturning = ref(false);
const borrowingHistory = ref<BorrowingHistoryRecord[]>([]);
const isHistoryLoading = ref(true);
const historyError = ref("");
const deleteError = ref("");
const isDeleting = ref(false);
const borrowForm = reactive({
  borrowerName: "",
  dueDate: "",
  note: "",
});

function toInputDate(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDate(value: string | null) {
  if (!value) {
    return "未設定";
  }

  const date = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(date);
}

async function loadHistory() {
  if (!book.value) {
    return;
  }

  isHistoryLoading.value = true;
  historyError.value = "";
  try {
    borrowingHistory.value = await getBookBorrowingHistory(book.value.id);
  } catch (error) {
    historyError.value = error instanceof Error
      ? error.message
      : "目前無法載入借閱歷史，請稍後再試。";
  } finally {
    isHistoryLoading.value = false;
  }
}

function openBorrowForm() {
  const defaultDueDate = new Date();
  defaultDueDate.setDate(defaultDueDate.getDate() + 14);
  borrowForm.borrowerName = "";
  borrowForm.dueDate = toInputDate(defaultDueDate);
  borrowForm.note = "";
  borrowError.value = "";
  borrowerError.value = "";
  isBorrowFormOpen.value = true;
}

function closeBorrowForm() {
  isBorrowFormOpen.value = false;
  borrowError.value = "";
  borrowerError.value = "";
}

async function submitBorrow() {
  borrowError.value = "";
  borrowerError.value = "";

  if (!borrowForm.borrowerName.trim()) {
    borrowerError.value = "請輸入借閱人，才能完成借出。";
    return;
  }

  if (!book.value) {
    return;
  }

  isSavingBorrow.value = true;
  try {
    book.value = await borrowBook(book.value.id, {
      borrowerName: borrowForm.borrowerName,
      dueDate: borrowForm.dueDate || null,
      note: borrowForm.note,
      clearDueDate: !borrowForm.dueDate,
    });
    await loadHistory();
    isBorrowFormOpen.value = false;
  } catch (error) {
    borrowError.value = error instanceof Error
      ? error.message
      : "目前無法完成借出，請稍後再試。";
  } finally {
    isSavingBorrow.value = false;
  }
}

async function markAsReturned() {
  if (!book.value) {
    return;
  }

  borrowError.value = "";
  isReturning.value = true;
  try {
    book.value = await returnBook(book.value.id);
    await loadHistory();
  } catch (error) {
    borrowError.value = error instanceof Error
      ? error.message
      : "目前無法完成歸還，請稍後再試。";
  } finally {
    isReturning.value = false;
  }
}

async function deleteCurrentBook() {
  if (!book.value || !window.confirm(
    `確定要刪除「${book.value.title}」嗎？刪除後會移至資源回收筒，30 天內可以還原。`,
  )) {
    return;
  }

  deleteError.value = "";
  isDeleting.value = true;
  try {
    await deleteBook(book.value.id);
    await router.push("/books");
  } catch (error) {
    deleteError.value = error instanceof Error
      ? error.message
      : "目前無法刪除書籍，請稍後再試。";
  } finally {
    isDeleting.value = false;
  }
}

const coverFile = ref<File | null>(null);
const coverMessage = ref("");
const coverError = ref("");
const isCoverSaving = ref(false);

async function loadBook() {
  try {
    book.value = await getBook(String(route.params.id));
    await loadHistory();
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : "找不到這本書。";
  } finally {
    isLoading.value = false;
  }
}

async function replaceCover(file: File | null) {
  coverMessage.value = "";
  coverError.value = "";
  if (!file || !book.value) {
    return;
  }

  isCoverSaving.value = true;
  try {
    book.value = await uploadBookCover(book.value.id, file);
    coverFile.value = null;
    coverMessage.value = "封面已更新。";
  } catch (error) {
    coverError.value = error instanceof Error
      ? error.message
      : "目前無法更新封面，請稍後再試。";
  } finally {
    isCoverSaving.value = false;
  }
}

async function removeCover() {
  if (!book.value?.coverUrl) {
    return;
  }

  coverMessage.value = "";
  coverError.value = "";
  isCoverSaving.value = true;
  try {
    await removeBookCover(book.value.id);
    book.value = { ...book.value, coverUrl: null };
    coverMessage.value = "封面已移除。";
  } catch (error) {
    coverError.value = error instanceof Error
      ? error.message
      : "目前無法移除封面，請稍後再試。";
  } finally {
    isCoverSaving.value = false;
  }
}

onMounted(loadBook);
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
      <div class="detail-header-actions">
        <StatusBadge :status="book.status" />
        <div class="detail-actions desktop-only">
          <button class="button button-secondary" type="button" @click="router.push(`/books/${book.id}/edit`)">
            修改資料
          </button>
          <button class="button button-danger" type="button" :disabled="isDeleting" @click="deleteCurrentBook">
            {{ isDeleting ? "刪除中⋯" : "刪除書籍" }}
          </button>
        </div>
      </div>
    </div>

    <p v-if="deleteError" class="feedback feedback-error" role="alert">{{ deleteError }}</p>

    <section class="detail-card cover-card">
      <BookCoverPicker
        v-model="coverFile"
        input-id-prefix="detail-book-cover"
        :current-cover-url="book.coverUrl"
        @update:model-value="replaceCover"
        @remove="removeCover"
      />
      <p v-if="isCoverSaving" class="cover-status" role="status">封面處理中⋯</p>
      <p v-if="coverMessage" class="feedback feedback-success" role="status">{{ coverMessage }}</p>
      <p v-if="coverError" class="feedback feedback-error" role="alert">{{ coverError }}</p>
    </section>

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

    <section class="detail-card borrowing-card" aria-labelledby="borrowing-title">
      <div class="detail-card-heading">
        <div>
          <p class="detail-label">目前借閱</p>
          <h2 id="borrowing-title">借閱狀態</h2>
        </div>
        <button
          v-if="book.status === 'HOME'"
          class="button button-primary"
          type="button"
          @click="openBorrowForm"
        >
          借出
        </button>
        <button
          v-else
          class="button button-secondary"
          type="button"
          :disabled="isReturning"
          @click="markAsReturned"
        >
          {{ isReturning ? "歸還中⋯" : "已歸還" }}
        </button>
      </div>

      <p v-if="borrowError" class="feedback feedback-error" role="alert">{{ borrowError }}</p>

      <form v-if="isBorrowFormOpen" class="borrow-form" @submit.prevent="submitBorrow">
        <h3>借出書籍</h3>
        <label class="field">
          <span>借閱人（必填）</span>
          <input
            v-model="borrowForm.borrowerName"
            type="text"
            autocomplete="off"
            :aria-invalid="!!borrowerError"
            aria-describedby="borrower-error"
          />
          <small v-if="borrowerError" id="borrower-error" class="field-error">{{ borrowerError }}</small>
        </label>
        <label class="field">
          <span>預計歸還日期</span>
          <span class="date-field">
            <input v-model="borrowForm.dueDate" type="date" />
            <button class="button button-text" type="button" @click="borrowForm.dueDate = ''">清除日期</button>
          </span>
        </label>
        <label class="field">
          <span>借出備註</span>
          <textarea v-model="borrowForm.note" rows="3" placeholder="例如：下星期還"></textarea>
        </label>
        <div class="form-actions">
          <button class="button button-secondary" type="button" @click="closeBorrowForm">取消</button>
          <button class="button button-primary" type="submit" :disabled="isSavingBorrow">
            {{ isSavingBorrow ? "借出中⋯" : "確認借出" }}
          </button>
        </div>
      </form>

      <dl v-else-if="book.currentBorrowing" class="metadata-list borrowing-details">
        <div><dt>借閱人</dt><dd>{{ book.currentBorrowing.borrowerName }}</dd></div>
        <div><dt>借出日期</dt><dd>{{ formatDate(book.currentBorrowing.borrowDateUtc) }}</dd></div>
        <div><dt>預計歸還日期</dt><dd>{{ formatDate(book.currentBorrowing.dueDate) }}</dd></div>
        <div v-if="book.currentBorrowing.note"><dt>借出備註</dt><dd>{{ book.currentBorrowing.note }}</dd></div>
      </dl>
      <p v-else class="empty-borrowing">目前沒有借閱中的資料</p>
    </section>

    <section class="detail-card borrowing-history-card" aria-labelledby="borrowing-history-title">
      <div class="detail-card-heading">
        <div>
          <p class="detail-label">完整流轉</p>
          <h2 id="borrowing-history-title">借閱歷史</h2>
        </div>
        <span class="section-note">{{ borrowingHistory.length }} 筆紀錄</span>
      </div>

      <p v-if="historyError" class="feedback feedback-error" role="alert">{{ historyError }}</p>
      <p v-else-if="isHistoryLoading" class="loading-inline" role="status">正在載入歷史⋯</p>
      <div v-else-if="borrowingHistory.length" class="detail-history-list">
        <article
          v-for="record in borrowingHistory"
          :key="record.id"
          class="detail-history-record"
          :data-history-status="record.status"
        >
          <div class="detail-history-heading">
            <strong>{{ record.status === "CURRENT" ? "目前借閱" : "已歸還" }}</strong>
            <span>{{ formatDate(record.borrowDateUtc) }}</span>
          </div>
          <dl class="metadata-list history-metadata">
            <div><dt>借閱人</dt><dd>{{ record.borrowerName }}</dd></div>
            <div><dt>預計歸還日期</dt><dd>{{ formatDate(record.dueDate) }}</dd></div>
            <div><dt>實際歸還日期</dt><dd>{{ formatDate(record.returnedAtUtc) }}</dd></div>
            <div v-if="record.note"><dt>借出備註</dt><dd>{{ record.note }}</dd></div>
          </dl>
        </article>
      </div>
      <p v-else class="empty-borrowing">這本書還沒有借閱紀錄</p>
    </section>

    <section v-if="book.notes" class="detail-card notes-card">
      <p class="detail-label">備註</p>
      <p class="notes-value">{{ book.notes }}</p>
    </section>
  </section>
</template>
