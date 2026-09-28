<script setup lang="ts">
defineProps<{
  /** 圖示名稱，全部採用線條式 SVG，顏色跟著文字的 currentColor 走。 */
  name: "location" | "search" | "chevron" | "clock" | "alert" | "book" | "stack" | "send" | "bell" | "menu" | "close" | "settings";
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
    <template v-else-if="name === 'book'">
      <path d="M12 5.5C9 3.5 5.5 3.5 2.5 4.5v15c3-1 6.5-1 9.5 1 3-2 6.5-2 9.5-1v-15c-3-1-6.5-1-9.5 1Zm0 0v15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else-if="name === 'stack'">
      <path d="M5 4h16l-3 5H5a2.5 2.5 0 0 1 0-5Zm0 5a2.5 2.5 0 0 0 0 5h13l3-5M5 14a2.5 2.5 0 0 0 0 5h13l3-5M18 9v5m0 0v5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else-if="name === 'send'">
      <path d="m3 10 18-7-7 18-3-8-8-3Zm8 3L21 3" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else-if="name === 'bell'">
      <path d="M6.5 16.5h11l-1.2-1.8V10a4.3 4.3 0 0 0-8.6 0v4.7l-1.2 1.8ZM10 19h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
    </template>
    <template v-else-if="name === 'menu'">
      <path d="M4 6h16M4 12h16M4 18h16" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'close'">
      <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else-if="name === 'settings'">
      <path d="M4 7h16M4 17h16M8 4v6M16 14v6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
    </template>
    <template v-else>
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.8" />
      <path d="M12 8v4.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
      <circle cx="12" cy="15.8" r="1" fill="currentColor" />
    </template>
  </svg>
</template>
