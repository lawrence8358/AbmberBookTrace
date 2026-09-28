<script setup lang="ts">
import { ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import AppIcon from "./AppIcon.vue";

const route = useRoute();
const panel = ref<HTMLElement | null>(null);
const isOpen = ref(false);
watch(() => route.fullPath, () => panel.value?.hidePopover());
</script>

<template>
  <button class="icon-button header-menu-button mobile-only" type="button" popovertarget="header-menu" aria-label="開啟功能選單" aria-controls="header-menu" :aria-expanded="isOpen"><AppIcon name="menu" /></button>
  <section id="header-menu" ref="panel" class="header-popover menu-popover" popover="auto" aria-labelledby="header-menu-title" @toggle="isOpen = panel?.matches(':popover-open') ?? false">
    <div class="popover-heading">
      <h2 id="header-menu-title">我的書房</h2>
      <button class="icon-button" type="button" popovertarget="header-menu" popovertargetaction="hide" aria-label="關閉功能選單"><AppIcon name="close" /></button>
    </div>
    <nav class="menu-links" aria-label="功能選單" @click="panel?.hidePopover()">
      <RouterLink to="/books">我的書庫</RouterLink>
      <RouterLink to="/borrowings">借閱歷史</RouterLink>
      <RouterLink to="/notifications">提醒</RouterLink>
      <RouterLink to="/recycle-bin">資源回收筒</RouterLink>
      <RouterLink class="menu-settings" to="/settings">設定</RouterLink>
    </nav>
  </section>
</template>
