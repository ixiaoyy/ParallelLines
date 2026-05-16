<script setup lang="ts">
withDefaults(defineProps<{ tone?: "blue" | "green" | "gray" | "amber" }>(), { tone: "gray" });
</script>

<template>
  <a-tag class="badge" :class="`badge--${tone}`" :bordered="false">
    <slot />
  </a-tag>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 0.2rem;
  padding: 0.12rem 0.38rem;
  font-size: 0.74rem;
  font-weight: 600;
}

.badge--blue {
  color: var(--primary-hover);
  background: var(--bg-selected);
}

.badge--green {
  color: var(--accent-geek);
  background: var(--bg-hover);
}

.badge--amber {
  color: var(--warning);
  background: var(--pinned-bg);
}

.badge--gray {
  color: var(--muted);
  background: var(--bg-subtle);
}
</style>
