<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute } from "vue-router";
import { isSignedIn, openChangePassword, requestLogin, signOut } from "../auth";
import AppIcon from "./AppIcon.vue";

const route = useRoute();
const panel = ref<HTMLElement | null>(null);
const isOpen = ref(false);
watch(() => route.fullPath, () => panel.value?.hidePopover());

function choose(action: () => void) {
  panel.value?.hidePopover();
  action();
}
</script>

<template>
  <button
    class="reader-profile"
    type="button"
    popovertarget="account-menu"
    aria-haspopup="dialog"
    aria-controls="account-menu"
    :aria-expanded="isOpen"
    :aria-label="isSignedIn ? 'Amber 的私人書房，目前已登入' : 'Amber 的私人書房，目前未登入'"
  >
    <span class="reader-avatar-wrap" aria-hidden="true">
      <span class="reader-avatar"><img src="/images/reading-girl.webp" width="768" height="512" alt="" /></span>
      <span v-if="isSignedIn" class="reader-status-dot"></span>
    </span>
    <span class="desktop-only">Amber</span>
  </button>
  <section id="account-menu" ref="panel" class="header-popover account-popover" popover="auto" role="dialog" aria-labelledby="account-menu-title" @toggle="isOpen = panel?.matches(':popover-open') ?? false">
    <div class="popover-heading">
      <div>
        <h2 id="account-menu-title">Amber 的私人書房</h2>
        <p>{{ isSignedIn ? "已登入，可以新增、修改、刪除與借出書籍。" : "目前未登入，只能瀏覽與搜尋書籍。" }}</p>
      </div>
      <button class="icon-button" type="button" popovertarget="account-menu" popovertargetaction="hide" aria-label="關閉帳號選單"><AppIcon name="close" /></button>
    </div>
    <div class="account-actions">
      <template v-if="isSignedIn">
        <button class="button button-secondary" type="button" @click="choose(openChangePassword)">變更密碼</button>
        <button class="button button-secondary" type="button" @click="choose(signOut)">登出</button>
      </template>
      <button v-else class="button button-primary" type="button" @click="choose(() => requestLogin())">登入</button>
    </div>
  </section>
</template>
