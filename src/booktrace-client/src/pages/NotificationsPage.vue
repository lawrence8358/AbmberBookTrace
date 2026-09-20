<script setup lang="ts">
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import ReminderList from "../components/ReminderList.vue";
import { getReminders, type BorrowingReminder } from "../api";

const reminders = ref<BorrowingReminder[]>([]);
const isLoading = ref(true);
const errorMessage = ref("");

async function loadReminders() {
  isLoading.value = true;
  errorMessage.value = "";

  try {
    reminders.value = await getReminders();
  } catch (error) {
    errorMessage.value = error instanceof Error
      ? error.message
      : "目前無法載入提醒，請稍後再試。";
  } finally {
    isLoading.value = false;
  }
}

onMounted(() => {
  void loadReminders();
});
</script>

<template>
  <section class="page-heading compact-heading">
    <div>
      <p class="eyebrow">只在書蹤裡提醒你</p>
      <h1>提醒</h1>
      <p class="intro">到期日當天與逾期借閱會在這裡出現，不會寄送 Email、簡訊或手機推播。</p>
    </div>
    <RouterLink class="button button-secondary" to="/borrowings">查看借閱歷史</RouterLink>
  </section>

  <p v-if="errorMessage" class="feedback feedback-error" role="alert">{{ errorMessage }}</p>
  <div v-else-if="isLoading" class="loading-state" role="status">正在檢查借閱提醒⋯</div>

  <section v-else-if="reminders.length" class="notifications-results" aria-labelledby="notifications-title">
    <div class="section-heading-row">
      <div>
        <p class="eyebrow">需要留意</p>
        <h2 id="notifications-title">目前提醒</h2>
      </div>
      <span class="section-note">{{ reminders.length }} 則</span>
    </div>
    <ReminderList :reminders="reminders" />
  </section>

  <section v-else class="empty-state notifications-empty" aria-labelledby="empty-notifications-title">
    <div class="empty-illustration" aria-hidden="true">🌿</div>
    <h2 id="empty-notifications-title">目前沒有需要處理的提醒</h2>
    <p>有借閱紀錄在今天到期或超過期限時，提醒會出現在這裡。</p>
    <RouterLink class="button button-primary" to="/borrowings">查看借閱歷史</RouterLink>
  </section>
</template>
