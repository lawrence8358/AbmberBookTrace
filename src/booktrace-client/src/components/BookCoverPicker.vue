<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

const MAX_COVER_SIZE = 5 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);

const props = withDefaults(defineProps<{
  modelValue: File | null;
  currentCoverUrl?: string | null;
  inputIdPrefix?: string;
}>(), {
  currentCoverUrl: null,
  inputIdPrefix: "cover",
});

const emit = defineEmits<{
  "update:modelValue": [file: File | null];
  remove: [];
}>();

const coverError = ref("");
const localPreviewUrl = ref<string | null>(null);
const previewUrl = computed(() => localPreviewUrl.value ?? props.currentCoverUrl);
const galleryInputId = computed(() => `${props.inputIdPrefix}-gallery-input`);
const cameraInputId = computed(() => `${props.inputIdPrefix}-camera-input`);

watch(() => props.modelValue, (file) => {
  if (localPreviewUrl.value) {
    URL.revokeObjectURL(localPreviewUrl.value);
  }

  localPreviewUrl.value = file ? URL.createObjectURL(file) : null;
}, { immediate: true });

onBeforeUnmount(() => {
  if (localPreviewUrl.value) {
    URL.revokeObjectURL(localPreviewUrl.value);
  }
});

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] ?? null;
  input.value = "";

  if (!file) {
    return;
  }

  const validationError = validateFile(file);
  if (validationError) {
    coverError.value = validationError;
    emit("update:modelValue", null);
    return;
  }

  coverError.value = "";
  emit("update:modelValue", file);
}

function clearSelectedFile() {
  coverError.value = "";
  emit("update:modelValue", null);
}

function requestRemove() {
  coverError.value = "";
  emit("remove");
}

function validateFile(file: File): string {
  if (!ACCEPTED_TYPES.has(file.type)) {
    return "封面只接受 JPG、PNG、GIF 或 WebP 圖片。";
  }

  if (file.size > MAX_COVER_SIZE) {
    return "封面圖片不可超過 5 MB。";
  }

  return "";
}
</script>

<template>
  <div class="cover-picker">
    <div class="cover-preview" :class="{ 'cover-preview-empty': !previewUrl }">
      <img v-if="previewUrl" :src="previewUrl" alt="書籍封面預覽" />
      <span v-else>尚未上傳封面</span>
    </div>

    <div class="cover-picker-content">
      <p class="cover-picker-title">封面圖片</p>
      <p class="cover-picker-help">可選擇 JPG、PNG、GIF 或 WebP，檔案上限 5 MB。</p>
      <div class="cover-picker-actions">
        <label class="button button-secondary cover-picker-button" :for="galleryInputId">
          從相簿選擇
        </label>
        <input
          :id="galleryInputId"
          class="cover-file-input"
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          aria-label="從相簿選擇封面圖片"
          @change="chooseFile"
        />

        <label class="button button-secondary cover-picker-button" :for="cameraInputId">
          使用相機拍攝
        </label>
        <input
          :id="cameraInputId"
          class="cover-file-input"
          type="file"
          accept="image/*"
          capture="environment"
          aria-label="使用相機拍攝封面圖片"
          @change="chooseFile"
        />
      </div>
      <div class="cover-picker-actions cover-picker-secondary-actions">
        <button v-if="modelValue" class="text-button" type="button" @click="clearSelectedFile">
          清除選擇
        </button>
        <button v-else-if="currentCoverUrl" class="text-button text-button-danger" type="button" @click="requestRemove">
          移除封面
        </button>
      </div>
      <p v-if="coverError" class="field-error" role="alert">{{ coverError }}</p>
    </div>
  </div>
</template>
