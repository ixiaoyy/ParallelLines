<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { resolveApiAssetUrl } from "@/shared/api/client";

const props = defineProps<{
  src?: string | null;
  name: string;
  size?: "sm" | "md" | "lg";
  role?: string | null;
  level?: number | null;
}>();

type AvatarFrame = "none" | "level-1" | "level-2" | "level-3" | "level-4" | "level-5" | "ultimate";

const imageFailed = ref(false);
// initials 用途：头像图片缺失时显示单字兜底，避免中文双字在小头像里挤压溢出；无副作用。
const initials = computed(() => props.name.trim().slice(0, 1).toUpperCase() || "?");
const resolvedSrc = computed(() => resolveApiAssetUrl(props.src));
const displaySrc = computed(() => (imageFailed.value ? undefined : resolvedSrc.value));
const frame = computed<AvatarFrame>(() => {
  if (props.role === "admin") {
    return "ultimate";
  }

  const level = Math.max(0, props.level ?? 0);

  if (level >= 10) {
    return "ultimate";
  }
  if (level >= 9) {
    return "level-5";
  }
  if (level >= 7) {
    return "level-4";
  }
  if (level >= 5) {
    return "level-3";
  }
  if (level >= 3) {
    return "level-2";
  }
  if (level >= 1) {
    return "level-1";
  }

  return "none";
});
const hasLevelFrame = computed(() => frame.value !== "none");

watch(
  () => props.src,
  () => {
    imageFailed.value = false;
  },
);

function handleImageError() {
  imageFailed.value = true;
}
</script>

<template>
  <span
    class="avatar"
    :class="[
      `avatar--${size ?? 'md'}`,
      `avatar--frame-${frame}`,
      { 'avatar--level-frame': hasLevelFrame },
    ]"
    :title="name"
  >
    <img v-if="displaySrc" :src="displaySrc" alt="" aria-hidden="true" @error="handleImageError" />
    <span v-else class="ant-avatar-string">{{ initials }}</span>
  </span>
</template>

<style scoped>
.avatar {
  --avatar-core-bg: var(--btn-primary-bg);
  --avatar-frame-shadow: rgba(80, 220, 255, 0.28);

  position: relative;
  display: inline-flex !important;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  aspect-ratio: 1;
  overflow: hidden;
  border: 2px solid var(--bg-surface);
  border-radius: 50%;
  color: white !important;
  font-weight: 800;
  line-height: 1 !important;
  background: var(--avatar-core-bg) !important;
  box-shadow: 0 8px 18px rgba(17, 24, 39, 0.12);
}

.avatar img {
  position: relative;
  z-index: 3;
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
}

.avatar .ant-avatar-string {
  position: absolute !important;
  inset: 0 !important;
  z-index: 3;
  display: grid !important;
  place-items: center !important;
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
  border-color: transparent;
  color: var(--primary) !important;
  background: transparent !important;
  box-shadow:
    0 0 16px var(--avatar-frame-shadow);
}

.avatar--level-frame img {
  background: var(--bg-surface);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.86);
}

.avatar--level-frame .ant-avatar-string {
  border-radius: inherit;
  background: var(--bg-surface);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.86);
}

.avatar--level-frame::after {
  position: absolute;
  z-index: 2;
  inset: -32%;
  border-radius: inherit;
  background-repeat: no-repeat;
  background-position: center;
  background-size: contain;
  filter:
    drop-shadow(0 0 4px rgba(160, 245, 255, 0.72))
    drop-shadow(0 0 12px var(--avatar-frame-shadow));
  pointer-events: none;
  animation: ice-frame-pulse 2.6s ease-in-out infinite;
  content: "";
}

.avatar--frame-level-1 {
  --avatar-frame-shadow: rgba(96, 199, 255, 0.24);
}

.avatar--frame-level-1::after {
  background-image: url("../assets/avatar-frames/level-1.webp");
}

.avatar--frame-level-2 {
  --avatar-frame-shadow: rgba(96, 199, 255, 0.28);
}

.avatar--frame-level-2::after {
  background-image: url("../assets/avatar-frames/level-2.webp");
}

.avatar--frame-level-3 {
  --avatar-frame-shadow: rgba(80, 220, 255, 0.32);
}

.avatar--frame-level-3::after {
  background-image: url("../assets/avatar-frames/level-3.webp");
}

.avatar--frame-level-4 {
  --avatar-frame-shadow: rgba(80, 220, 255, 0.36);
}

.avatar--frame-level-4::after {
  background-image: url("../assets/avatar-frames/level-4.webp");
}

.avatar--frame-level-5,
.avatar--frame-ultimate {
  --avatar-frame-shadow: rgba(80, 220, 255, 0.46);
}

.avatar--frame-level-5::before,
.avatar--frame-ultimate::before {
  position: absolute;
  z-index: 1;
  inset: -34%;
  border-radius: inherit;
  background: conic-gradient(
    from 0deg,
    transparent 0deg,
    transparent 22deg,
    rgba(220, 255, 255, 0.9) 30deg,
    rgba(80, 220, 255, 0.68) 36deg,
    transparent 48deg,
    transparent 90deg,
    rgba(170, 245, 255, 0.7) 104deg,
    transparent 120deg,
    transparent 180deg,
    rgba(255, 255, 255, 0.86) 194deg,
    transparent 214deg,
    transparent 360deg
  );
  opacity: 0.88;
  pointer-events: none;
  animation: ice-frame-rotate 3.8s linear infinite;
  content: "";
  mask: radial-gradient(circle, transparent 0 44%, black 48% 62%, transparent 66% 100%);
  -webkit-mask: radial-gradient(circle, transparent 0 44%, black 48% 62%, transparent 66% 100%);
}

.avatar--frame-level-5::after {
  background-image: url("../assets/avatar-frames/level-5.webp");
}

.avatar--frame-ultimate::after {
  background-image: url("../assets/avatar-frames/ultimate-animated.webp");
  animation-duration: 2.2s;
}

@keyframes ice-frame-rotate {
  to {
    transform: rotate(1turn);
  }
}

@keyframes ice-frame-pulse {
  0%,
  100% {
    opacity: 0.96;
    transform: scale(1);
  }

  50% {
    opacity: 1;
    transform: scale(1.035);
  }
}

@media (prefers-reduced-motion: reduce) {
  .avatar--level-frame::before,
  .avatar--level-frame::after {
    animation: none;
  }
}
</style>
