<script setup lang="ts">
import { computed } from "vue";

import { useAdminPlugins, useUpdateAdminPlugin } from "@/features/plugins/queries";
import UiCard from "@/shared/ui/Card.vue";

const pluginsQuery = useAdminPlugins();
const updatePlugin = useUpdateAdminPlugin();
const plugins = computed(() => pluginsQuery.data.value ?? []);

function togglePlugin(pluginId: string, enabled: boolean) {
  updatePlugin.mutate({ pluginId, payload: { enabled, config: {} } });
}
</script>

<template>
  <UiCard class="admin-plugins-panel">
    <template #title>插件与扩展点</template>
    <template #extra>
      <span class="plugin-count">{{ plugins.length }} 个插件</span>
    </template>

    <div v-if="pluginsQuery.isLoading.value" class="plugin-muted">正在加载插件注册表…</div>
    <div v-else-if="pluginsQuery.isError.value" class="plugin-error">插件配置读取失败，请稍后重试。</div>
    <div v-else class="plugin-list">
      <article v-for="plugin in plugins" :key="plugin.id" class="plugin-card">
        <div>
          <strong>{{ plugin.name }}</strong>
          <small>v{{ plugin.version }}</small>
        </div>
        <button
          class="plugin-toggle"
          type="button"
          :class="{ 'is-enabled': plugin.enabled }"
          :disabled="updatePlugin.isPending.value"
          @click="togglePlugin(plugin.id, !plugin.enabled)"
        >
          {{ plugin.enabled ? "已启用" : "启用" }}
        </button>
      </article>
    </div>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminPluginsPanel.scss"></style>
