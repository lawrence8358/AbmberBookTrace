<script setup lang="ts">
import { RouterLink } from "vue-router";
import type { BorrowingReminder } from "../api";

defineProps<{
  reminders: BorrowingReminder[];
}>();

function formatDate(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat("zh-TW", {
    year: "numeric",
    month: "numeric",
    day: "numeric",
  }).format(new Date(year, month - 1, day));
}
</script>

<template>
  <div class="reminder-list">
    <article
      v-for="reminder in reminders"
      :key="reminder.borrowingRecordId"
      class="reminder-card"
      :class="reminder.reminderType === 'OVERDUE' ? 'reminder-card-overdue' : 'reminder-card-due'"
      :data-reminder-type="reminder.reminderType"
    >
      <div class="reminder-icon" aria-hidden="true">{{ reminder.reminderType === "OVERDUE" ? "!" : "◷" }}</div>
      <div class="reminder-content">
        <p class="reminder-type">
          {{ reminder.reminderType === "OVERDUE" ? "逾期通知" : "今天到期" }}
        </p>
        <h3><RouterLink :to="`/books/${reminder.bookId}`">{{ reminder.bookTitle }}</RouterLink></h3>
        <p class="reminder-detail">
          借給 {{ reminder.borrowerName }} · 預計歸還 {{ formatDate(reminder.dueDate) }}
          <template v-if="reminder.reminderType === 'OVERDUE'"> · 已逾期 {{ reminder.daysOverdue }} 天</template>
        </p>
      </div>
    </article>
  </div>
</template>
