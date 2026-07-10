<script setup lang="ts">
import {
  ExclamationCircleOutlined,
  LoadingOutlined,
  LockOutlined,
  LoginOutlined,
} from "@ant-design/icons-vue";
import { computed } from "vue";
import type { RouteLocationRaw } from "vue-router";

const props = defineProps<{
  kind: "loading" | "error" | "login" | "forbidden";
  title?: string;
  description?: string;
  actionTo?: RouteLocationRaw;
  actionLabel?: string;
}>();

const defaultCopy = {
  loading: {
    title: "正在确认后台权限",
    description: "请稍候，正在读取当前账号信息。",
  },
  error: {
    title: "暂时无法确认账号状态",
    description: "请检查网络后刷新页面重试。",
  },
  login: {
    title: "需要登录后访问后台",
    description: "请使用管理员账号登录。",
  },
  forbidden: {
    title: "当前账号没有后台权限",
    description: "后台数据和用户管理仅限管理员访问。",
  },
} as const;

const copy = computed(() => ({
  title: props.title ?? defaultCopy[props.kind].title,
  description: props.description ?? defaultCopy[props.kind].description,
}));
const icon = computed(() => {
  if (props.kind === "loading") {
    return LoadingOutlined;
  }
  if (props.kind === "login") {
    return LoginOutlined;
  }
  if (props.kind === "forbidden") {
    return LockOutlined;
  }
  return ExclamationCircleOutlined;
});
</script>

<template>
  <section class="admin-access-state" :class="`is-${kind}`" :aria-live="kind === 'loading' ? 'polite' : undefined">
    <span class="admin-access-state__icon" aria-hidden="true">
      <component :is="icon" :spin="kind === 'loading'" />
    </span>
    <div>
      <h1>{{ copy.title }}</h1>
      <p>{{ copy.description }}</p>
      <div v-if="actionTo || $slots.actions" class="admin-access-state__actions">
        <RouterLink v-if="actionTo" class="admin-access-state__link" :to="actionTo">
          {{ actionLabel || "继续" }}
        </RouterLink>
        <slot name="actions" />
      </div>
    </div>
  </section>
</template>

<style scoped lang="scss" src="./AdminAccessState.scss"></style>
