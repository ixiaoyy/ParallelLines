<template>
  <a-card class="ui-card" :bordered="false">
    <slot />
  </a-card>
</template>

<style scoped>
.ui-card {
  border: 1px solid rgba(229, 231, 235, 0.92);
  border-radius: var(--radius-card);
  background: rgba(255, 255, 255, 0.88);
  box-shadow: var(--shadow-card);
}

.ui-card :deep(.ant-card-body) {
  padding: 0;
}
</style>
