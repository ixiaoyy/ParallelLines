<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  src?: string | null;
  name: string;
  size?: "sm" | "md" | "lg";
  role?: string | null;
  level?: number | null;
}>();

type AvatarFrame = "none" | "bronze" | "silver" | "gold" | "diamond" | "crystal" | "admin";

const initials = props.name.slice(0, 2).toUpperCase();
const frame = computed<AvatarFrame>(() => {
  if (props.role === "admin") {
    return "admin";
  }

  const level = Math.max(0, props.level ?? 0);
  if (level >= 9) {
    return "crystal";
  }
  if (level >= 7) {
    return "diamond";
  }
  if (level >= 5) {
    return "gold";
  }
  if (level >= 3) {
    return "silver";
  }
  if (level >= 1) {
    return "bronze";
  }

  return "none";
});
const hasLevelFrame = computed(() => frame.value !== "none" && frame.value !== "admin");
</script>

<template>
  <a-avatar
    class="avatar"
    :class="[
      `avatar--${size ?? 'md'}`,
      `avatar--frame-${frame}`,
      { 'avatar--admin': frame === 'admin', 'avatar--level-frame': hasLevelFrame },
    ]"
    :src="src || undefined"
  >
    {{ src ? "" : initials }}
  </a-avatar>
</template>

<style scoped>
.avatar {
  --avatar-core-bg: var(--btn-primary-bg);
  --avatar-frame-ring: transparent;
  --avatar-frame-shadow: rgba(var(--shadow-rgb), 0.12);

  position: relative;
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border: 2px solid var(--bg-surface);
  color: white !important;
  font-weight: 800;
  background: var(--avatar-core-bg) !important;
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

.avatar--level-frame {
  overflow: visible;
  isolation: isolate;
  border-color: var(--bg-surface);
  box-shadow:
    0 0 0 2px var(--avatar-frame-ring),
    0 8px 20px var(--avatar-frame-shadow);
}

.avatar--frame-bronze {
  --avatar-frame-ring: color-mix(in srgb, var(--accent-coral) 70%, var(--accent-gold));
  --avatar-frame-shadow: rgba(var(--accent-coral-rgb), 0.2);
}

.avatar--frame-silver {
  --avatar-frame-ring: color-mix(in srgb, var(--muted) 72%, var(--bg-surface));
  --avatar-frame-shadow: rgba(var(--muted-rgb), 0.24);
}

.avatar--frame-gold {
  --avatar-frame-ring: var(--accent-gold);
  --avatar-frame-shadow: rgba(var(--accent-gold-rgb), 0.26);
}

.avatar--frame-diamond {
  --avatar-frame-ring: var(--btn-primary-bg);
  --avatar-frame-shadow: rgba(var(--primary-rgb), 0.24);
}

.avatar--frame-crystal {
  --avatar-frame-ring: color-mix(in srgb, var(--brand-cyan) 76%, var(--bg-surface));
  --avatar-frame-shadow: rgba(var(--primary-rgb), 0.28);
}

.avatar--admin {
  overflow: visible;
  isolation: isolate;
  border-color: var(--bg-surface);
  box-shadow:
    0 0 0 2px var(--btn-primary-bg),
    0 0 0 4px rgba(var(--accent-gold-rgb), 0.7),
    0 10px 24px rgba(var(--primary-rgb), 0.2),
    0 0 18px rgba(var(--accent-geek-rgb), 0.18);
}

.avatar--admin::before {
  position: absolute;
  z-index: -1;
  inset: -0.28rem;
  border-radius: inherit;
  background: conic-gradient(
    from 120deg,
    rgba(var(--primary-rgb), 0.85),
    rgba(var(--accent-gold-rgb), 0.78),
    rgba(var(--accent-geek-rgb), 0.72),
    rgba(var(--primary-rgb), 0.85)
  );
  opacity: 0.46;
  filter: blur(6px);
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
