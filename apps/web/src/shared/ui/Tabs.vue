<script setup lang="ts">
import { Tabs as ATabs, TabPane as ATabPane } from "ant-design-vue";
defineProps<{ tabs: Array<{ key: string; label: string }>; modelValue: string }>();
defineEmits<{ "update:modelValue": [value: string] }>();
</script>

<template>
  <ATabs
    class="tabs"
    :active-key="modelValue"
    type="card"
    @change="(key: string | number) => $emit('update:modelValue', String(key))"
  >
    <ATabPane v-for="tab in tabs" :key="tab.key" :tab="tab.label" />
  </ATabs>
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
  border-color: var(--btn-primary-border) !important;
  background: var(--btn-primary-bg) !important;
}

.tabs :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
  color: var(--btn-primary-fg) !important;
}
</style>
