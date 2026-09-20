<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="header-inner">
        <RouterLink class="brand" to="/books" aria-label="書蹤首頁">
          <span class="brand-mark" aria-hidden="true">✦</span>
          <span>
            <strong>書蹤</strong>
            <small>找到我的每一本書</small>
          </span>
        </RouterLink>
        <nav class="main-nav" aria-label="主要導覽">
          <RouterLink to="/books">我的書庫</RouterLink>
          <RouterLink class="nav-primary" to="/books/new">新增書籍</RouterLink>
        </nav>
      </div>
    </header>

    <main class="main-content">
      <RouterView />
    </main>
  </div>
</template>
