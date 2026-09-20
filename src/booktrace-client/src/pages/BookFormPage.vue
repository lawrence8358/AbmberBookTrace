<script setup lang="ts">
import { reactive, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";
import { createBook } from "../api";

const router = useRouter();
const isSaving = ref(false);
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

async function saveBook() {
  titleError.value = "";
  formError.value = "";

  if (!form.title.trim()) {
    titleError.value = "請輸入書名，才能保存這本書。";
    return;
  }

  isSaving.value = true;
  try {
    const book = await createBook(form);
    await router.push(`/books/${book.id}`);
  } catch (error) {
    formError.value = error instanceof Error
      ? error.message
      : "目前無法保存書籍，請稍後再試。";
  } finally {
    isSaving.value = false;
  }
}
</script>

<template>
  <section class="form-page">
    <div class="page-heading compact-heading">
      <div>
        <p class="eyebrow">把新書放進書房</p>
        <h1>新增書籍</h1>
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
        <RouterLink class="button button-secondary" to="/books">取消</RouterLink>
        <button class="button button-primary" type="submit" :disabled="isSaving">
          {{ isSaving ? "保存中⋯" : "儲存書籍" }}
        </button>
      </div>
    </form>
  </section>
</template>
