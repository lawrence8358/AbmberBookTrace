<script setup lang="ts">
import type { BookStatus } from "../api";

defineProps<{ status: BookStatus }>();
</script>

<template>
  <span class="status-badge" :class="status === 'BORROWED' ? 'status-borrowed' : 'status-home'">
    <span aria-hidden="true">●</span>
    {{ status === "BORROWED" ? "借出中" : "在家" }}
  </span>
</template>
