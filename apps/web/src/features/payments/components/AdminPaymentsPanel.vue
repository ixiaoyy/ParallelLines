<script setup lang="ts">
import { computed } from "vue";

import { useAdminPaymentEvents } from "@/features/payments/queries";
import { relativeTime } from "@/shared/lib/format";
import UiCard from "@/shared/ui/Card.vue";

const eventsQuery = useAdminPaymentEvents();
const events = computed(() => eventsQuery.data.value ?? []);
</script>

<template>
  <UiCard class="admin-payments-panel">
    <div class="payments-heading">
      <div>
        <span>Billing events</span>
        <h2>支付事件</h2>
      </div>
      <small>{{ events.length }} 条最近事件</small>
    </div>

    <div v-if="eventsQuery.isLoading.value" class="payments-state">正在读取支付事件…</div>
    <div v-else-if="eventsQuery.isError.value" class="payments-state payments-state--error">
      支付事件暂时不可用。
    </div>
    <div v-else-if="!events.length" class="payments-state">暂无支付 webhook 事件。</div>
    <table v-else class="payments-table">
      <thead>
        <tr>
          <th>事件</th>
          <th>Provider</th>
          <th>状态</th>
          <th>时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="event in events" :key="event.id">
          <td>{{ event.event_type }}</td>
          <td>{{ event.provider }}</td>
          <td>{{ event.status }}</td>
          <td>{{ event.processed_at ? relativeTime(event.processed_at) : "未处理" }}</td>
        </tr>
      </tbody>
    </table>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminPaymentsPanel.scss"></style>
