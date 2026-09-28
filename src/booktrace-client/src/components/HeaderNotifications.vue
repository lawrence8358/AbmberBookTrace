<script setup lang="ts">
import { ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { getReminders, type BorrowingReminder } from "../api";
import ReminderList from "./ReminderList.vue";
import AppIcon from "./AppIcon.vue";

const route = useRoute();
const panel = ref<HTMLElement | null>(null);
const closeButton = ref<HTMLButtonElement | null>(null);
const isOpen = ref(false);
const isLoading = ref(false);
const errorMessage = ref("");
const reminders = ref<BorrowingReminder[]>([]);
let requestId = 0;

async function loadReminders() {
  const currentRequest = ++requestId;
  isLoading.value = true;
  errorMessage.value = "";
  try {
    const result = await getReminders();
    if (currentRequest === requestId) reminders.value = result;
  } catch (error) {
    if (currentRequest === requestId) {
      errorMessage.value = error instanceof Error ? error.message : "目前無法載入提醒，請再試一次。";
    }
  } finally {
    if (currentRequest === requestId) isLoading.value = false;
  }
}

function onToggle() {
  isOpen.value = panel.value?.matches(":popover-open") ?? false;
  if (isOpen.value) {
    closeButton.value?.focus();
    void loadReminders();
  } else {
    ++requestId;
  }
}

watch(() => route.fullPath, () => panel.value?.hidePopover());

function closeAfterNavigation(event: MouseEvent) {
  if (event.target instanceof Element && event.target.closest("a")) panel.value?.hidePopover();
}
</script>

<template>
  <button class="header-alert" type="button" popovertarget="header-notifications" aria-label="查看提醒" aria-haspopup="dialog" aria-controls="header-notifications" :aria-expanded="isOpen">
    <AppIcon name="bell" />
  </button>
  <section id="header-notifications" ref="panel" class="header-popover notification-popover" popover="auto" role="dialog" aria-labelledby="header-notifications-title" @toggle="onToggle" @click="closeAfterNavigation">
    <div class="popover-heading">
      <div>
        <h2 id="header-notifications-title">書房提醒</h2>
        <p>到期與逾期借閱，都在這裡。</p>
      </div>
      <button ref="closeButton" class="icon-button" type="button" popovertarget="header-notifications" popovertargetaction="hide" aria-label="關閉提醒"><AppIcon name="close" /></button>
    </div>
    <div v-if="isLoading" class="popover-loading" role="status">正在查看借閱狀態⋯</div>
    <div v-else-if="errorMessage" class="popover-error">
      <p role="alert">{{ errorMessage }}</p>
      <button class="button button-secondary" type="button" @click="loadReminders">重新載入</button>
    </div>
    <ReminderList v-else-if="reminders.length" :reminders="reminders" />
    <div v-else class="notification-empty">
      <img src="/images/reading-cat.webp" width="768" height="512" alt="" />
      <h3>目前沒有需要處理的提醒</h3>
      <p>書房一切安好，安心讀本書吧。<br />有到期或逾期借閱時，會顯示在這裡。</p>
    </div>
    <div class="popover-footer"><RouterLink class="text-link" to="/borrowings">查看借閱歷史 <AppIcon name="chevron" /></RouterLink></div>
  </section>
</template>
