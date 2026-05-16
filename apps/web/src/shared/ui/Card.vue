<template>
  <a-card class="ui-card" :bordered="false">
    <slot />
  </a-card>
</template>

<style scoped>
.ui-card {
  border: 1px solid var(--border);
  border-radius: var(--radius-card);
  background: var(--bg-surface);
  box-shadow: var(--shadow-card);
}

.ui-card :deep(.ant-card-body) {
  padding: 0;
}
</style>
