<script setup lang="ts">
import { ref } from "vue";
import { changePassword, closeChangePassword } from "../auth";
import ModalDialog from "./ModalDialog.vue";

const MIN_PASSWORD_LENGTH = 4;

const currentPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const errorMessage = ref("");
const isSubmitting = ref(false);
const isDone = ref(false);

async function submit() {
  if (isSubmitting.value) return;

  if (!currentPassword.value) {
    errorMessage.value = "請輸入目前的密碼。";
  } else if (newPassword.value.length < MIN_PASSWORD_LENGTH) {
    errorMessage.value = `新密碼至少需要 ${MIN_PASSWORD_LENGTH} 個字。`;
  } else if (newPassword.value === currentPassword.value) {
    errorMessage.value = "新密碼不能和目前的密碼相同。";
  } else if (newPassword.value !== confirmPassword.value) {
    errorMessage.value = "兩次輸入的新密碼不一樣。";
  } else {
    errorMessage.value = "";
  }
  if (errorMessage.value) return;

  isSubmitting.value = true;
  try {
    await changePassword(currentPassword.value, newPassword.value);
    isDone.value = true;
    currentPassword.value = newPassword.value = confirmPassword.value = "";
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "目前無法變更密碼，請稍後再試。";
  } finally {
    isSubmitting.value = false;
  }
}
</script>

<template>
  <ModalDialog title="變更密碼" title-id="change-password-title" @cancel="closeChangePassword">
    <template v-if="isDone">
      <p class="feedback feedback-success auth-done" role="status">密碼已經更新，下次登入請使用新密碼。</p>
      <div class="confirm-actions">
        <button class="button button-primary" type="button" @click="closeChangePassword">關閉</button>
      </div>
    </template>
    <template v-else>
      <p class="auth-lead">換成新的密碼後，下次登入就用新密碼。密碼至少 {{ MIN_PASSWORD_LENGTH }} 個字。</p>
      <form class="auth-form" novalidate @submit.prevent="submit">
        <label class="field">
          <span>目前的密碼</span>
          <input v-model="currentPassword" type="password" autocomplete="current-password" autofocus />
        </label>
        <label class="field">
          <span>新密碼</span>
          <input v-model="newPassword" type="password" autocomplete="new-password" />
        </label>
        <label class="field">
          <span>再輸入一次新密碼</span>
          <input v-model="confirmPassword" type="password" autocomplete="new-password" />
        </label>
        <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
        <div class="confirm-actions">
          <button class="button button-secondary" type="button" @click="closeChangePassword">取消</button>
          <button class="button button-primary" type="submit" :disabled="isSubmitting">{{ isSubmitting ? "儲存中⋯" : "變更密碼" }}</button>
        </div>
      </form>
    </template>
  </ModalDialog>
</template>
