<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { createBook, getBook, removeBookCover, updateBook, uploadBookCover } from "../api";
import BookCoverPicker from "../components/BookCoverPicker.vue";

const route = useRoute();
const router = useRouter();
const isEdit = computed(() => Boolean(route.params.id));
const bookId = computed(() => Number(route.params.id));
const isLoading = ref(isEdit.value);
const isSaving = ref(false);
const coverFile = ref<File | null>(null);
const currentCoverUrl = ref<string | null>(null);
const shouldRemoveCover = ref(false);
const titleError = ref("");
const formError = ref("");
const form = reactive({
  title: "",
  author: "",
  isbn: "",
  publisher: "",
  category: "",
  location: "",
  detailedLocation: "",
  notes: "",
});

async function loadBook() {
  if (!isEdit.value) {
    isLoading.value = false;
    return;
  }

  try {
    const book = await getBook(String(route.params.id));
    form.title = book.title;
    form.author = book.author ?? "";
    form.isbn = book.isbn ?? "";
    form.publisher = book.publisher ?? "";
    form.category = book.category ?? "";
    form.location = book.location ?? "";
    form.detailedLocation = book.detailedLocation ?? "";
    form.notes = book.notes ?? "";
    currentCoverUrl.value = book.coverUrl;
  } catch (error) {
    formError.value = error instanceof Error ? error.message : "找不到這本書。";
  } finally {
    isLoading.value = false;
  }
}

function handleCoverSelected(file: File | null) {
  coverFile.value = file;
  if (file) {
    shouldRemoveCover.value = false;
  }
}

function removeCurrentCover() {
  currentCoverUrl.value = null;
  shouldRemoveCover.value = true;
}

async function saveBook() {
  titleError.value = "";
  formError.value = "";

  if (!form.title.trim()) {
    titleError.value = "請輸入書名，才能保存這本書。";
    return;
  }

  isSaving.value = true;
  try {
    const book = isEdit.value
      ? await updateBook(bookId.value, form)
      : await createBook(form);
    if (coverFile.value) {
      await uploadBookCover(book.id, coverFile.value);
    } else if (isEdit.value && shouldRemoveCover.value) {
      await removeBookCover(book.id);
    }
    await router.push(`/books/${book.id}`);
  } catch (error) {
    formError.value = error instanceof Error
      ? error.message
      : "目前無法保存書籍，請稍後再試。";
  } finally {
    isSaving.value = false;
  }
}

onMounted(() => {
  void loadBook();
});
</script>

<template>
  <section v-if="isLoading" class="loading-state" role="status">正在載入書籍資料⋯</section>
  <section v-else-if="formError && isEdit && !form.title" class="feedback feedback-error" role="alert">{{ formError }}</section>
  <section v-else class="form-page">
    <div class="page-heading compact-heading">
      <div>
        <p class="eyebrow">{{ isEdit ? "整理書房資料" : "把新書放進書房" }}</p>
        <h1>{{ isEdit ? "修改書籍" : "新增書籍" }}</h1>
        <p class="intro">書名是唯一必填欄位，其餘資訊可以之後再補。</p>
      </div>
    </div>

    <form class="book-form" @submit.prevent="saveBook">
      <div v-if="formError" class="feedback feedback-error" role="alert">{{ formError }}</div>

      <div class="form-section">
        <h2>基本資料</h2>
        <div class="form-grid">
          <label class="field field-wide">
            <span id="title-label">書名（必填）</span>
            <input v-model="form.title" type="text" autocomplete="off" aria-labelledby="title-label" :aria-invalid="!!titleError" aria-describedby="title-error" />
            <small v-if="titleError" id="title-error" class="field-error">{{ titleError }}</small>
          </label>
          <label class="field">
            <span>作者</span>
            <input v-model="form.author" type="text" />
          </label>
          <label class="field">
            <span>ISBN</span>
            <input v-model="form.isbn" type="text" inputmode="numeric" />
          </label>
          <label class="field">
            <span>出版社</span>
            <input v-model="form.publisher" type="text" />
          </label>
          <label class="field">
            <span>分類／標籤</span>
            <input v-model="form.category" type="text" />
          </label>
        </div>
      </div>

      <div class="form-section">
        <h2>封面</h2>
        <BookCoverPicker
          :model-value="coverFile"
          :current-cover-url="currentCoverUrl"
          :input-id-prefix="isEdit ? 'edit-book-cover' : 'new-book-cover'"
          @update:model-value="handleCoverSelected"
          @remove="removeCurrentCover"
        />
      </div>

      <div class="form-section">
        <h2>放在哪裡</h2>
        <div class="form-grid">
          <label class="field">
            <span>位置</span>
            <input v-model="form.location" type="text" placeholder="例如：客廳書櫃" />
          </label>
          <label class="field">
            <span>詳細位置</span>
            <input v-model="form.detailedLocation" type="text" placeholder="例如：第二層左側" />
          </label>
        </div>
      </div>

      <div class="form-section">
        <h2>備註</h2>
        <label class="field">
          <span class="sr-only">備註</span>
          <textarea v-model="form.notes" rows="4" placeholder="記下版本、來源或想提醒自己的事"></textarea>
        </label>
      </div>

      <div class="form-actions">
        <RouterLink class="button button-secondary" :to="isEdit ? `/books/${bookId}` : '/books'">取消</RouterLink>
        <button class="button button-primary" type="submit" :disabled="isSaving">
          {{ isSaving ? "保存中⋯" : isEdit ? "儲存修改" : "儲存書籍" }}
        </button>
      </div>
    </form>
  </section>
</template>
