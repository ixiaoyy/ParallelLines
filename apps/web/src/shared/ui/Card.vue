<template>
  <div class="ui-card">
    <div class="ant-card-body ui-card__body">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.ui-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
}

.ui-card__body {
  padding: 0;
}
</style>
