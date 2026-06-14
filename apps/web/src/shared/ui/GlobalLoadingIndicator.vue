<script setup lang="ts">
import { useIsFetching, useIsMutating } from "@tanstack/vue-query";
import { computed, ref, watch } from "vue";

import { useApiRequestActivity } from "@/shared/api/client";

const apiPendingCount = useApiRequestActivity();
const fetchingCount = useIsFetching();
const mutatingCount = useIsMutating();
const visible = ref(false);
const pendingCount = computed(
  () => apiPendingCount.value + fetchingCount.value + mutatingCount.value,
);
let showTimer: number | undefined;
let hideTimer: number | undefined;

watch(
  pendingCount,
  (count) => {
    window.clearTimeout(showTimer);
    window.clearTimeout(hideTimer);

    if (count > 0) {
      if (!visible.value) {
        showTimer = window.setTimeout(() => {
          visible.value = true;
        }, 180);
      }
      return;
    }

    if (visible.value) {
      hideTimer = window.setTimeout(() => {
        visible.value = false;
      }, 260);
    }
  },
  { immediate: true },
);
</script>

<template>
  <Transition name="global-loading">
    <div
      v-if="visible"
      class="global-loading-indicator"
      role="status"
      aria-live="polite"
      aria-label="接口处理中"
    >
      <span class="global-loading-indicator__mark" aria-hidden="true">
        <i></i>
        <i></i>
        <i></i>
      </span>
      <span class="global-loading-indicator__copy">处理中</span>
    </div>
  </Transition>
</template>

<style scoped lang="scss" src="./GlobalLoadingIndicator.scss"></style>
