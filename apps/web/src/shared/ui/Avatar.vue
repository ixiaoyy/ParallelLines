<script setup lang="ts">
const props = defineProps<{
  src?: string | null;
  name: string;
  size?: "sm" | "md" | "lg";
  role?: string | null;
}>();

const initials = props.name.slice(0, 2).toUpperCase();
</script>

<template>
  <a-avatar
    class="avatar"
    :class="[`avatar--${size ?? 'md'}`, { 'avatar--admin': role === 'admin' }]"
    :src="src || undefined"
  >
    {{ src ? "" : initials }}
  </a-avatar>
</template>

<style scoped>
.avatar {
  position: relative;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 2px solid white;
  color: white !important;
  font-weight: 800;
  background: linear-gradient(135deg, var(--primary), var(--accent-geek));
  box-shadow: 0 8px 18px rgba(17, 24, 39, 0.12);
}

.avatar :deep(img) {
  border-radius: inherit;
}

.avatar :deep(.ant-avatar-string) {
  position: static !important;
  transform: none !important;
  line-height: 1 !important;
}

.avatar--sm {
  width: 2rem;
  height: 2rem;
  font-size: 0.75rem;
}

.avatar--md {
  width: 2.55rem;
  height: 2.55rem;
}

.avatar--lg {
  width: 3.4rem;
  height: 3.4rem;
  font-size: 1.1rem;
}

.avatar--admin {
  overflow: visible;
  isolation: isolate;
  border-color: rgba(255, 255, 255, 0.96);
  box-shadow:
    0 0 0 1px rgba(var(--primary-rgb), 0.24),
    0 10px 24px rgba(var(--primary-rgb), 0.2),
    0 0 18px rgba(var(--accent-geek-rgb), 0.18);
}

.avatar--admin::before {
  position: absolute;
  z-index: -1;
  inset: -0.32rem;
  border-radius: inherit;
  background: conic-gradient(
    from 120deg,
    rgba(var(--primary-rgb), 0.85),
    rgba(var(--accent-gold-rgb), 0.78),
    rgba(var(--accent-geek-rgb), 0.72),
    rgba(var(--primary-rgb), 0.85)
  );
  opacity: 0.62;
  filter: blur(5px);
  animation: admin-avatar-orbit 4.8s linear infinite;
  content: "";
}

.avatar--admin::after {
  position: absolute;
  right: -0.16rem;
  bottom: -0.12rem;
  width: 0.58rem;
  height: 0.58rem;
  border: 2px solid var(--bg-surface);
  border-radius: 999px;
  background:
    radial-gradient(circle at 35% 35%, var(--bg-surface) 0 20%, transparent 22%),
    linear-gradient(135deg, var(--btn-primary-bg), var(--accent-geek));
  box-shadow:
    0 0 0 1px rgba(var(--primary-rgb), 0.24),
    0 4px 10px rgba(var(--primary-rgb), 0.24);
  content: "";
}

@keyframes admin-avatar-orbit {
  to {
    transform: rotate(1turn);
  }
}

@media (prefers-reduced-motion: reduce) {
  .avatar--admin::before {
    animation: none;
  }
}

</style>
