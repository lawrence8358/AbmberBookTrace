<script setup lang="ts">
import { computed, ref } from "vue";
import { auth, closeLogin, createAccount, signIn } from "../auth";
import ModalDialog from "./ModalDialog.vue";

const MIN_PASSWORD_LENGTH = 4;
const MAX_ACCOUNT_LENGTH = 50;

// 資料庫裡還沒有任何帳號時，登入視窗改成讓第一位使用者建立帳號。
const isSetup = computed(() => auth.setupRequired);
const userName = ref("");
const password = ref("");
const confirmPassword = ref("");
const errorMessage = ref("");
const isSubmitting = ref(false);

function validationProblem() {
  if (!userName.value.trim()) return "請輸入帳號。";
  if (!password.value) return "請輸入密碼。";
  if (!isSetup.value) return "";
  if (userName.value.trim().length > MAX_ACCOUNT_LENGTH) return `帳號不能超過 ${MAX_ACCOUNT_LENGTH} 個字。`;
  if (userName.value.includes(":")) return "帳號不能包含冒號（:）。";
  if (password.value.length < MIN_PASSWORD_LENGTH) return `密碼至少需要 ${MIN_PASSWORD_LENGTH} 個字。`;
  if (password.value !== confirmPassword.value) return "兩次輸入的密碼不一樣。";
  return "";
}

async function submit() {
  if (isSubmitting.value) return;

  errorMessage.value = validationProblem();
  if (errorMessage.value) return;

  isSubmitting.value = true;
  try {
    if (isSetup.value) await createAccount(userName.value, password.value);
    else await signIn(userName.value, password.value);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "目前無法登入，請稍後再試。";
    password.value = confirmPassword.value = "";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <ModalDialog :title="isSetup ? '建立帳號' : '登入'" title-id="login-title" @cancel="closeLogin">
    <p class="auth-lead">
      {{ isSetup ? "這個書房還沒有帳號。請建立一組帳號與密碼，之後就用它登入；建立後會自動登入。" : "登入後才能新增、修改、刪除與借出書籍。" }}
    </p>
    <form class="auth-form" novalidate @submit.prevent="submit">
      <label class="field">
        <span>帳號</span>
        <input v-model="userName" type="text" autocomplete="username" autocapitalize="none" spellcheck="false" autofocus />
      </label>
      <label class="field">
        <span>密碼<template v-if="isSetup">（至少 {{ MIN_PASSWORD_LENGTH }} 個字）</template></span>
        <input v-model="password" type="password" :autocomplete="isSetup ? 'new-password' : 'current-password'" />
      </label>
      <label v-if="isSetup" class="field">
        <span>再輸入一次密碼</span>
        <input v-model="confirmPassword" type="password" autocomplete="new-password" />
      </label>
      <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
      <div class="confirm-actions">
        <button class="button button-secondary" type="button" @click="closeLogin">取消</button>
        <button class="button button-primary" type="submit" :disabled="isSubmitting">
          {{ isSubmitting ? (isSetup ? "建立中⋯" : "登入中⋯") : (isSetup ? "建立帳號並登入" : "登入") }}
        </button>
      </div>
    </form>
  </ModalDialog>
</template>
