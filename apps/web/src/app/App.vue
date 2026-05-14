<script setup lang="ts">
import zhCN from "ant-design-vue/es/locale/zh_CN";

import AppShell from "@/app/layouts/AppShell.vue";

const theme = {
  token: {
    colorPrimary: "#3B82F6",
    colorSuccess: "#10B981",
    colorTextHeading: "#111827",
    colorText: "#4B5563",
    colorBgLayout: "#F8F9FA",
    colorBgContainer: "#FFFFFF",
    borderRadius: 16,
    fontFamily:
      '"LXGW WenKai Screen", "Noto Serif SC", ui-serif, Georgia, "Times New Roman", serif',
  },
  components: {
    Button: {
      borderRadius: 999,
      controlHeight: 40,
      fontWeight: 760,
    },
    Card: {
      borderRadiusLG: 16,
      boxShadowTertiary: "0 12px 30px rgba(17, 24, 39, 0.08)",
    },
  },
};
</script>

<template>
  <a-config-provider :locale="zhCN" :theme="theme">
    <AppShell>
      <RouterView />
    </AppShell>
  </a-config-provider>
</template>
