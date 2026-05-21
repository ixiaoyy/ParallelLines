<script setup lang="ts">
import { computed, reactive, watch } from "vue";

import { settingCategoryLabel } from "@/features/admin/model";
import type { SiteSettingResponse, SiteSettingValue } from "@/features/admin/model";
import { useAdminSettings, useUpdateAdminSetting } from "@/features/admin/queries";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const settingsQuery = useAdminSettings();
const updateSettingMutation = useUpdateAdminSetting();
const settingDrafts = reactive<Record<string, string | number | boolean>>({});

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

watch(
  settings,
  (items) => {
    for (const setting of items) {
      if (setting.data_type === "integer" && typeof setting.value === "number") {
        settingDrafts[setting.key] = setting.value;
      } else if (setting.data_type === "boolean") {
        settingDrafts[setting.key] = setting.value === true;
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
  settingDrafts[key] = (event.target as HTMLInputElement).value;
}

function onNumberSettingChange(key: string, event: Event) {
  settingDrafts[key] = Number((event.target as HTMLInputElement).value);
}

function saveSetting(setting: SiteSettingResponse) {
  const value = settingDrafts[setting.key] as SiteSettingValue;
  updateSettingMutation.mutate({ key: setting.key, payload: { value } });
}
</script>

<template>
  <UiCard class="settings-panel">
    <div class="section-head">
      <span class="panel-kicker">Site settings</span>
      <h2>站点设置</h2>
    </div>
    <p v-if="settingsQuery.isError.value" class="panel-state panel-state--error" role="alert">
      设置加载失败，请确认管理员权限。
    </p>
    <div v-else class="settings-groups">
      <section v-for="group in groupedSettings" :key="group.category" class="settings-group">
        <h3>{{ settingCategoryLabel(group.category) }}</h3>
        <article v-for="setting in group.items" :key="setting.key" class="setting-row">
          <div>
            <strong>{{ setting.key }}</strong>
            <span>{{ setting.description }}</span>
          </div>
          <label v-if="setting.data_type === 'boolean'" class="setting-control setting-control--toggle">
            <input
              type="checkbox"
              :checked="Boolean(settingDrafts[setting.key])"
              @change="onBooleanSettingChange(setting.key, $event)"
            />
            <span>{{ settingDrafts[setting.key] ? "开启" : "关闭" }}</span>
          </label>
          <input
            v-else-if="setting.data_type === 'integer'"
            class="setting-control"
            type="number"
            min="1"
            :value="Number(settingDrafts[setting.key] ?? 0)"
            @input="onNumberSettingChange(setting.key, $event)"
          />
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
