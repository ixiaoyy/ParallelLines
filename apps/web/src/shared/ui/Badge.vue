<script setup lang="ts">
withDefaults(defineProps<{ tone?: "blue" | "green" | "gray" | "amber" | "coral" }>(), { tone: "gray" });
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
  background: var(--cyan-soft);
}

.badge--green {
  color: #6f9c2e;
  background: var(--lime-soft);
}

.badge--amber {
  color: #c99220;
  background: var(--gold-soft);
}

.badge--coral {
  color: #d97a62;
  background: var(--coral-soft);
}

.badge--gray {
  color: var(--muted);
  background: var(--bg-subtle);
}
</style>
