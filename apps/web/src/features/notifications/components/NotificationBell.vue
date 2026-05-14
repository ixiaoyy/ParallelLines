<script setup lang="ts">
defineProps<{ count: number }>();
</script>

<template>
  <a-badge :count="count" :number-style="{ backgroundColor: '#10B981' }">
    <a-button class="bell" shape="circle" :aria-label="`通知，${count} 条未读`">
      <slot />
    </a-button>
  </a-badge>
</template>

<style scoped>
.bell {
  color: var(--primary) !important;
  background: white !important;
}
</style>
