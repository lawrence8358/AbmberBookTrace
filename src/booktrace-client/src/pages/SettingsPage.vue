<script setup lang="ts">
import { ref } from "vue";
import PageHeading from "../components/PageHeading.vue";
import { readingSize, setReadingSize } from "../readingPreferences";

const message = ref("");
function updateSize(value: "standard" | "large") {
  message.value = setReadingSize(value)
    ? "閱讀字級已儲存在這個瀏覽器。"
    : "字級已套用；此瀏覽器無法儲存設定，重新開啟後會恢復預設。";
}
</script>

<template>
  <PageHeading title="設定" description="讓書房讀起來更舒服。這些偏好只儲存在目前的瀏覽器。" />
  <section class="detail-card">
    <fieldset class="reading-size-options">
      <legend>閱讀字級</legend>
      <label><input type="radio" name="reading-size" value="standard" :checked="readingSize === 'standard'" @change="updateSize('standard')" /><span>標準<span class="setting-help">維持目前的清爽版面</span></span></label>
      <label><input type="radio" name="reading-size" value="large" :checked="readingSize === 'large'" @change="updateSize('large')" /><span>較大<span class="setting-help">放大頁面文字，方便閱讀</span></span></label>
    </fieldset>
    <p v-if="message" class="settings-message" role="status">{{ message }}</p>
  </section>
</template>
