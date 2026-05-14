<script setup lang="ts">
defineProps<{ tabs: Array<{ key: string; label: string }>; modelValue: string }>();
defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <a-tabs
    class="tabs"
    :active-key="modelValue"
    type="card"
    @change="(key: string | number) => $emit('update:modelValue', String(key))"
  >
    <a-tab-pane v-for="tab in tabs" :key="tab.key" :tab="tab.label" />
  </a-tabs>
</template>

<style scoped>
.tabs {
  max-width: max-content;
}

.tabs :deep(.ant-tabs-nav) {
  margin: 0;
}

.tabs :deep(.ant-tabs-tab) {
  border-radius: 999px !important;
  border: 1px solid var(--border) !important;
  background: rgba(255, 255, 255, 0.8) !important;
  font-weight: 760;
}

.tabs :deep(.ant-tabs-tab-active) {
  background: var(--primary) !important;
}

.tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: #fff !important;
}
</style>
