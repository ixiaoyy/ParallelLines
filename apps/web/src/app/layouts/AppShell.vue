<script setup lang="ts">

import { CloseOutlined, MenuOutlined, PlusOutlined, SearchOutlined } from "@ant-design/icons-vue";

import { computed, ref, watch } from "vue";

import { useRoute, useRouter } from "vue-router";

import type { RouteLocationRaw } from "vue-router";



import { useCurrentUser, useLogout } from "@/features/auth/queries";

import NotificationBell from "@/features/notifications/components/NotificationBell.vue";

import UiButton from "@/shared/ui/Button.vue";

const router = useRouter();

const route = useRoute();

const globalSearch = ref("");

const isNavOpen = ref(false);

const currentUserQuery = useCurrentUser();

const logout = useLogout();

const currentUser = computed(() => currentUserQuery.data.value);



interface NavItem {

  key: "latest" | "hot" | "boards" | "solved" | "votes" | "admin";

  label: string;

  to: RouteLocationRaw;

}



const navItems: NavItem[] = [

  { key: "latest", label: "最新", to: "/" },

  { key: "hot", label: "热榜", to: { name: "home", hash: "#hot" } },

  { key: "boards", label: "版块", to: "/boards" },

  { key: "solved", label: "优质", to: { name: "home", hash: "#solved" } },

  { key: "votes", label: "投票", to: { name: "home", hash: "#votes" } },

  { key: "admin", label: "审核", to: { name: "admin-moderation" } },

];



watch(

  () => route.fullPath,

  () => {

    closeNavigation();

  },

);



async function handleLogout() {

  await logout();

}



function submitGlobalSearch() {

  const q = globalSearch.value.trim();

  if (!q) {

    return;

  }



  closeNavigation();

  void router.push({ name: "search", query: { q } });

}



function toggleNavigation() {

  isNavOpen.value = !isNavOpen.value;

}



function closeNavigation() {

  isNavOpen.value = false;

}



function isNavItemActive(item: NavItem) {

  if (item.key === "latest") {

    return route.name === "home" && !route.hash;

  }



  if (item.key === "hot") {

    return route.name === "home" && route.hash === "#hot";

  }



  if (item.key === "solved") {

    return route.name === "home" && route.hash === "#solved";

  }



  if (item.key === "votes") {

    return route.name === "home" && route.hash === "#votes";

  }



  if (item.key === "boards") {

    return route.name === "board-directory" || route.name === "board-detail";

  }



  return route.name === "admin-moderation";

}

</script>



<template>

  <div class="app-shell">

    <header class="topbar">

      <RouterLink class="brand" to="/" aria-label="平行线首页">

        <span class="brand-mark">
          <img class="brand-logo" src="/logo-lines.png" alt="" aria-hidden="true" />
        </span>

        <span>

          <strong>平行线</strong>

          <small>让答案可追溯</small>

        </span>

      </RouterLink>



      <nav class="nav-links" aria-label="主导航">

        <RouterLink

          v-for="item in navItems"

          :key="item.key"

          :to="item.to"

          :class="{ 'is-active': isNavItemActive(item) }"

        >

          {{ item.label }}

        </RouterLink>

      </nav>



      <a-input

        class="search-box"

        v-model:value="globalSearch"

        placeholder="搜索主题、标签、作者"

        aria-label="搜索平行线"

        @press-enter="submitGlobalSearch"

      >

        <template #prefix>

          <SearchOutlined />

        </template>

      </a-input>



      <button

        class="nav-toggle"

        type="button"

        :aria-expanded="isNavOpen"

        aria-controls="mobile-navigation"

        :aria-label="isNavOpen ? '收起主导航' : '展开主导航'"

        @click="toggleNavigation"

      >

        <CloseOutlined v-if="isNavOpen" />

        <MenuOutlined v-else />

        <span>{{ isNavOpen ? "收起" : "导航" }}</span>

      </button>



      <div class="topbar-actions">

        <NotificationBell />

        <RouterLink v-if="!currentUser" class="auth-link" :to="{ name: 'auth' }">登录/注册</RouterLink>

        <template v-else>

          <RouterLink class="user-link" :to="{ name: 'user-profile', params: { username: currentUser.username } }">

            {{ currentUser.username }}

          </RouterLink>

          <button class="logout-button" type="button" @click="handleLogout">退出</button>

        </template>

        <RouterLink class="publish-link" :to="{ name: 'new-topic' }" aria-label="发布主题">

          <UiButton tone="primary">

            <template #icon>

              <PlusOutlined />

            </template>

            <span class="publish-label">发布主题</span>

          </UiButton>

        </RouterLink>

      </div>



      <div v-show="isNavOpen" id="mobile-navigation" class="mobile-nav-panel">

        <nav class="mobile-nav-links" aria-label="移动主导航">

          <RouterLink

            v-for="item in navItems"

            :key="item.key"

            :to="item.to"

            :class="{ 'is-active': isNavItemActive(item) }"

            @click="closeNavigation"

          >

            {{ item.label }}

          </RouterLink>

        </nav>



        <a-input

          v-model:value="globalSearch"

          class="mobile-search-box"

          placeholder="搜索主题、标签、作者"

          aria-label="移动端搜索平行线"

          @press-enter="submitGlobalSearch"

        >

          <template #prefix>

            <SearchOutlined />

          </template>

        </a-input>

      </div>

    </header>



    <main class="shell-main">

      <slot />

    </main>

  </div>

</template>



<style scoped lang="scss" src="./AppShell.scss"></style>

