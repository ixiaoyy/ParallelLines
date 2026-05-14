<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "primary" | "ghost" | "subtle" | "success";
    type?: "button" | "submit" | "reset";
  }>(),
  { tone: "primary", type: "button" },
);
</script>

<template>
  <a-button
    class="ui-button"
    :class="`ui-button--${tone}`"
    :type="tone === 'primary' ? 'primary' : 'default'"
    :html-type="type"
    shape="round"
  >
    <slot name="icon" />
    <slot />
  </a-button>
</template>

<style scoped>
.ui-button {
  display: inline-flex !important;
  align-items: center;
  gap: 0.45rem;
  font-weight: 760;
  transition:
    transform 160ms ease,
    box-shadow 160ms ease,
    background 160ms ease;
}

.ui-button:hover {
  transform: translateY(-1px);
}

.ui-button:focus-visible {
  outline: 3px solid rgba(59, 130, 246, 0.35);
  outline-offset: 2px;
}

.ui-button--primary {
  color: white !important;
  background: var(--primary) !important;
  box-shadow: 0 12px 24px rgba(59, 130, 246, 0.24);
}

.ui-button--primary:hover {
  background: var(--primary-hover) !important;
}

.ui-button--success {
  color: white !important;
  border-color: var(--accent-geek) !important;
  background: var(--accent-geek) !important;
  box-shadow: 0 12px 24px rgba(16, 185, 129, 0.22);
}

.ui-button--subtle {
  color: var(--primary) !important;
  border-color: transparent !important;
  background: rgba(59, 130, 246, 0.1) !important;
}

.ui-button--ghost {
  color: var(--text) !important;
  border-color: transparent !important;
  background: transparent !important;
}
</style>
