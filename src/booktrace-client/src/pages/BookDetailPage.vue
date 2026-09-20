<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { borrowBook, getBook, returnBook, type Book } from "../api";
import StatusBadge from "../components/StatusBadge.vue";

const route = useRoute();
const book = ref<Book | null>(null);
const isLoading = ref(true);
const errorMessage = ref("");
const borrowError = ref("");
const borrowerError = ref("");
const isBorrowFormOpen = ref(false);
const isSavingBorrow = ref(false);
const isReturning = ref(false);
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
  } catch (error) {
    borrowError.value = error instanceof Error
      ? error.message
      : "目前無法完成歸還，請稍後再試。";
  } finally {
    isReturning.value = false;
  }
}

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
      <StatusBadge :status="book.status" />
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

    <section v-if="book.notes" class="detail-card notes-card">
      <p class="detail-label">備註</p>
      <p class="notes-value">{{ book.notes }}</p>
    </section>
  </section>
</template>
