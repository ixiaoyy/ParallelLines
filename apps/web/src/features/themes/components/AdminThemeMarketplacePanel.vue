<script setup lang="ts">
import { computed, ref } from "vue";

import { usePublicSiteSettings, useUpdateAdminSetting } from "@/features/admin/queries";
import { THEME_PACKAGES, validateThemePackage } from "@/features/themes/model";
import type { ThemePackage } from "@/features/themes/model";
import { applySiteBranding } from "@/shared/theme/siteBranding";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const publicSettingsQuery = usePublicSiteSettings();
const updateSetting = useUpdateAdminSetting();
const selectedThemeId = ref(THEME_PACKAGES[0]?.id ?? "");
const status = ref("");
const selectedTheme = computed(() => THEME_PACKAGES.find((theme) => theme.id === selectedThemeId.value));

function previewTheme(theme: ThemePackage) {
  const issues = validateThemePackage(theme);
  if (issues.length) {
    status.value = `主题包被安全沙箱拒绝：${issues.join("、")}`;
    return;
  }
  applySiteBranding(publicSettingsQuery.data.value?.settings, theme.settings);
  selectedThemeId.value = theme.id;
  status.value = `${theme.name} 预览已应用，仅当前浏览器生效。`;
}

function rollbackPreview() {
  applySiteBranding(publicSettingsQuery.data.value?.settings);
  status.value = "已回滚到服务器主题。";
}

async function enableTheme() {
  const theme = selectedTheme.value;
  if (!theme) {
    return;
  }
  const issues = validateThemePackage(theme);
  if (issues.length) {
    status.value = `主题包被安全沙箱拒绝：${issues.join("、")}`;
    return;
  }
  for (const [key, value] of Object.entries(theme.settings)) {
    await updateSetting.mutateAsync({ key, payload: { value } });
  }
  status.value = `${theme.name} 已启用；公共设置已刷新。`;
}
</script>

<template>
  <UiCard class="theme-marketplace-panel">
    <div class="section-head">
      <div>
        <span class="panel-kicker">Theme marketplace</span>
        <h2>主题市场与安全沙箱</h2>
      </div>
      <small>当前支持内置主题包预览、启用与浏览器级回滚；拒绝脚本和不安全资源。</small>
    </div>

    <div class="theme-grid">
      <article v-for="theme in THEME_PACKAGES" :key="theme.id" :class="{ active: theme.id === selectedThemeId }">
        <div class="theme-swatches">
          <span :style="{ background: theme.settings.brand_primary_color }"></span>
          <span :style="{ background: theme.settings.brand_accent_color }"></span>
        </div>
        <strong>{{ theme.name }}</strong>
        <p>{{ theme.description }}</p>
        <div class="theme-actions">
          <UiButton tone="ghost" @click="previewTheme(theme)">预览</UiButton>
          <UiButton tone="subtle" @click="selectedThemeId = theme.id">选择</UiButton>
        </div>
      </article>
    </div>

    <div class="marketplace-actions">
      <UiButton tone="primary" :disabled="updateSetting.isPending.value" @click="enableTheme">
        {{ updateSetting.isPending.value ? "启用中…" : "启用所选主题" }}
      </UiButton>
      <UiButton tone="ghost" @click="rollbackPreview">回滚预览</UiButton>
    </div>
    <p v-if="status" class="theme-status" role="status">{{ status }}</p>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminThemeMarketplacePanel.scss"></style>
