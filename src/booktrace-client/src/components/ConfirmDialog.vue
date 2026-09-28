<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from "vue";

defineProps<{ title: string; description: string; confirmLabel: string }>();
const emit = defineEmits<{ confirm: []; cancel: [] }>();
const dialog = ref<HTMLDialogElement | null>(null);
let previousOverflow = "";
onMounted(() => {
  previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  dialog.value?.showModal();
});
onBeforeUnmount(() => { dialog.value?.close(); document.body.style.overflow = previousOverflow; });
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="book-confirm-dialog" aria-labelledby="confirm-title" aria-describedby="confirm-description" @cancel.prevent="emit('cancel')">
      <h2 id="confirm-title">{{ title }}</h2>
      <p id="confirm-description">{{ description }}</p>
      <div class="confirm-actions">
        <button autofocus class="button button-secondary" type="button" @click="emit('cancel')">取消</button>
        <button class="button button-danger" type="button" @click="emit('confirm')">{{ confirmLabel }}</button>
      </div>
    </dialog>
  </Teleport>
</template>
