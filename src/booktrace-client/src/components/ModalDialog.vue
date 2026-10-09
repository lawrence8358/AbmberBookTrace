<script lang="ts">
// 多個對話框同時存在時，只有第一個負責鎖住頁面捲動、最後一個關掉時才還原。
let openDialogs = 0;
let previousOverflow = "";
</script>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

defineProps<{ title: string; titleId: string }>();
const emit = defineEmits<{ cancel: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);

onMounted(() => {
  if (openDialogs++ === 0) {
    previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
  }
  dialog.value?.showModal();
});

onBeforeUnmount(() => {
  dialog.value?.close();
  if (--openDialogs === 0) document.body.style.overflow = previousOverflow;
});
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="book-confirm-dialog auth-dialog" :aria-labelledby="titleId" @cancel.prevent="emit('cancel')">
      <h2 :id="titleId">{{ title }}</h2>
      <slot />
    </dialog>
  </Teleport>
</template>
