<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { settingCategoryLabel } from "@/features/admin/model";
import type { SiteSettingResponse, SiteSettingValue } from "@/features/admin/model";
import { useAdminSettings, usePublicSiteSettings, useUpdateAdminSetting } from "@/features/admin/queries";
import { applySiteBranding } from "@/shared/theme/siteBranding";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const settingsQuery = useAdminSettings();
const publicSettingsQuery = usePublicSiteSettings();
const updateSettingMutation = useUpdateAdminSetting();
const settingDrafts = reactive<Record<string, string | number | boolean>>({});
const panelStatus = ref("");
const previewActive = ref(false);

const settings = computed(() => settingsQuery.data.value ?? []);
const groupedSettings = computed(() => {
  const groups = new Map<string, SiteSettingResponse[]>();
  for (const setting of settings.value) {
    const group = groups.get(setting.category) ?? [];
    group.push(setting);
    groups.set(setting.category, group);
  }
  return Array.from(groups.entries()).map(([category, items]) => ({ category, items }));
});
const canPreviewTheme = computed(() =>
  settings.value.some((setting) => setting.public && (setting.category === "brand" || setting.category === "text")),
);

watch(
  settings,
  (items) => {
    for (const setting of items) {
      if (setting.data_type === "integer" && typeof setting.value === "number") {
        settingDrafts[setting.key] = setting.value;
      } else if (setting.data_type === "boolean") {
        settingDrafts[setting.key] = setting.value === true;
      } else if (setting.data_type === "json") {
        settingDrafts[setting.key] = JSON.stringify(setting.value ?? {}, null, 2);
      } else if (typeof setting.value === "string") {
        settingDrafts[setting.key] = setting.value;
      }
    }
  },
  { immediate: true },
);

function onBooleanSettingChange(key: string, event: Event) {
  settingDrafts[key] = (event.target as HTMLInputElement).checked;
}

function onTextSettingChange(key: string, event: Event) {
  settingDrafts[key] = (event.target as HTMLInputElement | HTMLTextAreaElement).value;
}

function onNumberSettingChange(key: string, event: Event) {
  settingDrafts[key] = Number((event.target as HTMLInputElement).value);
}

function saveSetting(setting: SiteSettingResponse) {
  let value: SiteSettingValue;
  try {
    value = draftValue(setting);
  } catch (error) {
    panelStatus.value = error instanceof Error ? error.message : "设置格式不正确。";
    return;
  }

  panelStatus.value = "";
  updateSettingMutation.mutate(
    { key: setting.key, payload: { value } },
    {
      onSuccess: () => {
        panelStatus.value = `${setting.key} 已保存。`;
        if (setting.public && previewActive.value) {
          previewPublicBranding();
        }
      },
      onError: () => {
        panelStatus.value = "保存失败，请检查设置格式和管理员权限。";
      },
    },
  );
}

function previewPublicBranding() {
  const preview: Record<string, unknown> = {};
  try {
    for (const setting of settings.value) {
      if (setting.public && (setting.category === "brand" || setting.category === "text")) {
        preview[setting.key] = draftValue(setting);
      }
    }
  } catch (error) {
    panelStatus.value = error instanceof Error ? error.message : "设置格式不正确。";
    return;
  }

  applySiteBranding(publicSettingsQuery.data.value?.settings, preview);
  previewActive.value = true;
  panelStatus.value = "主题预览已应用，仅当前浏览器生效；保存后刷新全站生效。";
}

function rollbackThemePreview() {
  applySiteBranding(publicSettingsQuery.data.value?.settings);
  previewActive.value = false;
  panelStatus.value = "已回滚当前浏览器中的主题预览。";
}

function draftValue(setting: SiteSettingResponse): SiteSettingValue {
  const value = settingDrafts[setting.key];
  if (setting.data_type === "integer") {
    return typeof value === "number" ? value : Number(value);
  }
  if (setting.data_type === "boolean") {
    return value === true;
  }
  if (setting.data_type === "json") {
    if (typeof value !== "string") {
      throw new Error(`${setting.key} 需要 JSON 文本。`);
    }
    try {
      return JSON.parse(value) as SiteSettingValue;
    } catch {
      throw new Error(`${setting.key} 不是合法 JSON。`);
    }
  }
  return typeof value === "string" ? value : String(value ?? "");
}

function isColorSetting(setting: SiteSettingResponse) {
  return setting.key.endsWith("_color");
}

function isLongTextSetting(setting: SiteSettingResponse) {
  return setting.data_type === "json" || setting.key.endsWith("_body");
}

function colorInputValue(setting: SiteSettingResponse) {
  const value = String(settingDrafts[setting.key] ?? setting.value ?? "");
  return /^#[0-9a-fA-F]{6}$/.test(value) ? value : "#005AA8";
}
</script>

<template>
  <UiCard class="settings-panel">
    <div class="section-head">
      <div>
        <span class="panel-kicker">Site settings</span>
        <h2>站点设置</h2>
      </div>
      <div class="settings-actions">
        <UiButton tone="ghost" :disabled="!canPreviewTheme" @click="previewPublicBranding">预览主题</UiButton>
        <UiButton tone="subtle" :disabled="!previewActive" @click="rollbackThemePreview">回滚预览</UiButton>
      </div>
    </div>
    <p v-if="settingsQuery.isError.value" class="panel-state panel-state--error" role="alert">
      设置加载失败，请确认管理员权限。
    </p>
    <p v-if="panelStatus" class="panel-state" role="status">{{ panelStatus }}</p>
    <div v-if="!settingsQuery.isError.value && settingsQuery.isPending.value" class="panel-state">正在加载站点设置…</div>
    <div v-else-if="!settingsQuery.isError.value" class="settings-groups">
      <section v-for="group in groupedSettings" :key="group.category" class="settings-group">
        <h3>{{ settingCategoryLabel(group.category) }}</h3>
        <article v-for="setting in group.items" :key="setting.key" class="setting-row">
          <div>
            <strong>{{ setting.key }}</strong>
            <span>{{ setting.description }}</span>
            <small v-if="setting.public">公开设置，保存后普通页面会自动刷新。</small>
          </div>
          <label v-if="setting.data_type === 'boolean'" class="setting-control setting-control--toggle">
            <input
              type="checkbox"
              :checked="Boolean(settingDrafts[setting.key])"
              @change="onBooleanSettingChange(setting.key, $event)"
            />
            <span>{{ settingDrafts[setting.key] ? "开启" : "关闭" }}</span>
          </label>
          <div v-else-if="isColorSetting(setting)" class="setting-control-pair">
            <input
              class="setting-control setting-control--color"
              type="color"
              :value="colorInputValue(setting)"
              @input="onTextSettingChange(setting.key, $event)"
            />
            <input
              class="setting-control"
              type="text"
              :value="String(settingDrafts[setting.key] ?? '')"
              @input="onTextSettingChange(setting.key, $event)"
            />
          </div>
          <input
            v-else-if="setting.data_type === 'integer'"
            class="setting-control"
            type="number"
            min="1"
            :value="Number(settingDrafts[setting.key] ?? 0)"
            @input="onNumberSettingChange(setting.key, $event)"
          />
          <textarea
            v-else-if="isLongTextSetting(setting)"
            class="setting-control setting-control--textarea"
            :value="String(settingDrafts[setting.key] ?? '')"
            rows="5"
            @input="onTextSettingChange(setting.key, $event)"
          ></textarea>
          <input
            v-else
            class="setting-control"
            type="text"
            :value="String(settingDrafts[setting.key] ?? '')"
            @input="onTextSettingChange(setting.key, $event)"
          />
          <UiButton tone="subtle" :disabled="updateSettingMutation.isPending.value" @click="saveSetting(setting)">
            保存
          </UiButton>
        </article>
      </section>
    </div>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminSettingsPanel.scss"></style>
