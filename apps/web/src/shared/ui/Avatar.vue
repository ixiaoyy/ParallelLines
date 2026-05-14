<script setup lang="ts">
const props = defineProps<{
  src?: string | null;
  name: string;
  size?: "sm" | "md" | "lg";
}>();

const initials = props.name.slice(0, 2).toUpperCase();
</script>

<template>
  <a-avatar class="avatar" :class="`avatar--${size ?? 'md'}`" :src="src || undefined">
    {{ src ? "" : initials }}
  </a-avatar>
</template>

<style scoped>
.avatar {
  overflow: hidden;
  border: 2px solid white;
  color: white !important;
  font-weight: 800;
  background: linear-gradient(135deg, var(--primary), var(--accent-geek));
  box-shadow: 0 8px 18px rgba(17, 24, 39, 0.12);
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

</style>
