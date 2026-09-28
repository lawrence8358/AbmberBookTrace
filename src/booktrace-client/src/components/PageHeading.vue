<script setup lang="ts">
defineProps<{ title: string; description: string }>();
</script>

<template>
  <header class="page-heading journal-heading">
    <div class="journal-heading-content">
      <h1>{{ title }}</h1>
      <p class="intro">{{ description }}</p>
      <div v-if="$slots.default" class="journal-heading-actions"><slot /></div>
    </div>
    <img class="journal-heading-art" src="/images/reading-cat.webp" width="768" height="512" alt="" />
  </header>
</template>
