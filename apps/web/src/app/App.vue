<script setup lang="ts">
import zhCN from "ant-design-vue/es/locale/zh_CN";

import AppShell from "@/app/layouts/AppShell.vue";

const theme = {
  token: {
    colorPrimary: "#38BDF8",
    colorSuccess: "#22C55E",
    colorWarning: "#FBBF24",
    colorError: "#F87171",
    colorTextHeading: "#334155",
    colorText: "#475569",
    colorBgLayout: "#F8FAFC",
    colorBgContainer: "#FFFFFF",
    colorBorder: "#E2E8F0",
    colorLink: "#0EA5E9",
    colorLinkHover: "#38BDF8",
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
      boxShadowTertiary: "0 12px 24px rgba(61, 78, 94, 0.08)",
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
