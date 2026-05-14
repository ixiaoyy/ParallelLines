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
  border-radius: 999px;
  padding: 0.24rem 0.58rem;
  font-size: 0.78rem;
  font-weight: 760;
}

.badge--blue {
  color: #1d4ed8;
  background: rgba(59, 130, 246, 0.12);
}

.badge--green {
  color: #047857;
  background: rgba(16, 185, 129, 0.14);
}

.badge--amber {
  color: #b45309;
  background: rgba(245, 158, 11, 0.15);
}

.badge--gray {
  color: var(--muted);
  background: var(--bg-subtle);
}
</style>
