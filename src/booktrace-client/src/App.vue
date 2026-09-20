<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";
</script>

<template>
  <div class="app-shell">
    <aside class="desktop-sidebar" aria-label="主要導覽">
      <RouterLink class="brand sidebar-brand" to="/books" aria-label="書蹤首頁">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 6.5c0-1.1.9-2 2-2h10v14H7a2 2 0 0 1-2-2v-10Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
            <path d="M7 18.5h10M8.5 8.5h6M8.5 11.5h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </span>
        <span>
          <strong>書蹤</strong>
          <small>找到我的每一本書</small>
        </span>
      </RouterLink>

      <nav class="sidebar-nav" aria-label="書房導覽">
        <RouterLink class="sidebar-link" to="/books">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 5.5h12a2 2 0 0 1 2 2v11H7a2 2 0 0 1-2-2v-11Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M7 18.5h12M8.5 9h7M8.5 12h7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          </span>
          我的書庫
        </RouterLink>
        <RouterLink class="sidebar-link" to="/borrowings">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.8" /><path d="M12 8v4.5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" /></svg>
          </span>
          借閱歷史
        </RouterLink>
        <RouterLink class="sidebar-link" to="/notifications">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M6.5 16.5h11l-1.2-1.8V10a4.3 4.3 0 0 0-8.6 0v4.7l-1.2 1.8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M10 19h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          </span>
          提醒
        </RouterLink>
        <RouterLink class="sidebar-link desktop-only" to="/recycle-bin">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5.5 8.5h13v10h-13v-10ZM8 5.5h8l1 3H7l1-3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M9.5 12v3M14.5 12v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          </span>
          資源回收筒
        </RouterLink>
      </nav>

      <RouterLink class="sidebar-add button button-primary" to="/books/new">
        <span aria-hidden="true">＋</span>
        新增書籍
      </RouterLink>
    </aside>

    <div class="app-frame">
      <header class="site-header">
        <div class="header-inner">
          <RouterLink class="brand mobile-only" to="/books" aria-label="書蹤首頁">
            <span class="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 6.5c0-1.1.9-2 2-2h10v14H7a2 2 0 0 1-2-2v-10Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
                <path d="M7 18.5h10M8.5 8.5h6M8.5 11.5h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
              </svg>
            </span>
            <span>
              <strong>書蹤</strong>
              <small>找到我的每一本書</small>
            </span>
          </RouterLink>
          <p class="header-context desktop-only">我的私人書房</p>
          <RouterLink class="header-alert mobile-only" to="/notifications" aria-label="查看提醒">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.5 16.5h11l-1.2-1.8V10a4.3 4.3 0 0 0-8.6 0v4.7l-1.2 1.8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M10 19h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          </RouterLink>
          <RouterLink class="header-add desktop-only" to="/books/new">＋ 新增書籍</RouterLink>
        </div>
      </header>

      <main class="main-content">
        <RouterView />
      </main>

      <nav class="mobile-bottom-nav mobile-only" aria-label="手機導覽">
        <RouterLink class="bottom-nav-link" to="/books">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m4.5 11 7.5-6 7.5 6v7.5h-5v-4h-5v4h-5V11Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /></svg>
          <span>首頁</span>
        </RouterLink>
        <RouterLink class="bottom-nav-link" to="/books#library-search">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.5" cy="10.5" r="5.5" stroke="currentColor" stroke-width="1.8" /><path d="m15 15 4 4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          <span>搜尋</span>
        </RouterLink>
        <RouterLink class="bottom-nav-link bottom-nav-add" to="/books/new" aria-label="新增書籍">
          <span class="bottom-nav-add-icon" aria-hidden="true">＋</span>
          <span>新增</span>
        </RouterLink>
        <RouterLink class="bottom-nav-link" to="/borrowings">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 5.5h12a2 2 0 0 1 2 2v11H7a2 2 0 0 1-2-2v-11Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M7 18.5h12M8.5 9h7M8.5 12h7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          <span>歷史</span>
        </RouterLink>
        <RouterLink class="bottom-nav-link" to="/notifications">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6.5 16.5h11l-1.2-1.8V10a4.3 4.3 0 0 0-8.6 0v4.7l-1.2 1.8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M10 19h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          <span>提醒</span>
        </RouterLink>
        <RouterLink class="bottom-nav-link" to="/recycle-bin">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5.5 8.5h13v10h-13v-10ZM8 5.5h8l1 3H7l1-3Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" /><path d="M9.5 12v3M14.5 12v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
          <span>回收筒</span>
        </RouterLink>
      </nav>
    </div>
  </div>
</template>
