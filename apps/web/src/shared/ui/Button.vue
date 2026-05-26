<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: "primary" | "ghost" | "subtle" | "success" | "danger";
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
  >
    <slot name="icon" />
    <slot />
  </a-button>
</template>

<style scoped>
.ui-button {
  display: inline-flex !important;
  align-items: center;
  gap: 0.4rem;
  border-radius: 0.25rem !important;
  font-weight: 600;
  box-shadow: none !important;
  transition:
    border-color 180ms ease,
    background 180ms ease,
    box-shadow 180ms ease,
    transform 160ms ease;
}

.ui-button:focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}

.ui-button--primary:hover {
  transform: translateY(-1px);
}

.ui-button--success {
  color: #fff !important;
  border-color: var(--accent-geek) !important;
  background: var(--accent-geek) !important;
}

.ui-button--success:hover {
  border-color: #059669 !important;
  background: #059669 !important;
}

.ui-button--danger {
  color: var(--danger) !important;
  border-color: var(--danger-border) !important;
  background: var(--danger-bg) !important;
}

.ui-button--subtle {
  color: var(--primary) !important;
  border-color: transparent !important;
  background: var(--bg-selected) !important;
}

.ui-button--ghost {
  color: var(--text) !important;
  border-color: transparent !important;
  background: transparent !important;
}
</style>
