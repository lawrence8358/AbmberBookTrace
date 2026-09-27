<script setup lang="ts">
defineProps<{
  /** 圖示名稱，全部採用線條式 SVG，顏色跟著文字的 currentColor 走。 */
  name: "location" | "search" | "chevron" | "clock" | "alert";
}>();
</script>

<template>
  <svg class="app-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true" focusable="false">
    <template v-if="name === 'location'">
      <path
        d="M12 21s6.5-5.4 6.5-10.2A6.5 6.5 0 0 0 5.5 10.8C5.5 15.6 12 21 12 21Z"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linejoin="round"
      />
      <circle cx="12" cy="10.5" r="2.4" stroke="currentColor" stroke-width="1.8" />
    </template>
    <template v-else-if="name === 'search'">
      <circle cx="10.5" cy="10.5" r="5.5" stroke="currentColor" stroke-width="1.8" />
      <path d="m15 15 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'chevron'">
      <path d="m9.5 6 6 6-6 6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else-if="name === 'clock'">
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.8" />
      <path d="M12 8v4.5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else>
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.8" />
      <path d="M12 8v4.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <circle cx="12" cy="15.8" r="1" fill="currentColor" />
    </template>
  </svg>
</template>
