<script setup lang="ts">
import { Skeleton as ASkeleton } from "ant-design-vue";
</script>

<template>
  <ASkeleton class="skeleton" active :paragraph="{ rows: 2 }" />
</template>

<style scoped>
.skeleton {
  width: 100%;
}
</style>
