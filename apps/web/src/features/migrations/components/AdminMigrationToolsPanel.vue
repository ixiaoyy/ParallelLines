<script setup lang="ts">
import { computed, ref } from "vue";

import { fetchMigrationExport } from "@/features/migrations/api";
import type { MigrationExportResponse, MigrationImportRequest, MigrationImportResponse } from "@/features/migrations/model";
import { usePreviewMigrationImport, useRunMigrationImport } from "@/features/migrations/queries";
import UiCard from "@/shared/ui/Card.vue";

const samplePayload: MigrationImportRequest = {
  source: "discourse-json",
  users: [{ username: "imported_user", email: "imported_user@example.com" }],
  boards: [{ slug: "imported", name: "导入版块", description: "历史迁移内容" }],
  topics: [
    {
      external_id: "topic-1",
      board_slug: "imported",
      author_username: "imported_user",
      title: "迁移主题示例",
      slug: "imported-topic",
      tags: ["migration"],
      raw_md: "第一帖内容",
    },
  ],
  posts: [],
};

const importJson = ref(JSON.stringify(samplePayload, null, 2));
const parseError = ref("");
const lastResult = ref<MigrationImportResponse | null>(null);
const exportSnapshot = ref<MigrationExportResponse | null>(null);
const exportLoading = ref(false);
const exportError = ref("");
const previewMutation = usePreviewMigrationImport();
const runMutation = useRunMigrationImport();
const resultRows = computed(() => lastResult.value?.rows.slice(0, 8) ?? []);

async function previewImport() {
  const payload = parsePayload();
  if (!payload) {
    return;
  }
  lastResult.value = await previewMutation.mutateAsync(payload);
}

async function runImport() {
  const payload = parsePayload();
  if (!payload) {
    return;
  }
  lastResult.value = await runMutation.mutateAsync(payload);
}

async function loadExport() {
  exportError.value = "";
  exportLoading.value = true;
  try {
    exportSnapshot.value = await fetchMigrationExport();
  } catch (error) {
    exportError.value = error instanceof Error ? error.message : "导出失败";
  } finally {
    exportLoading.value = false;
  }
}

function parsePayload(): MigrationImportRequest | null {
  parseError.value = "";
  try {
    const parsed = JSON.parse(importJson.value) as MigrationImportRequest;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      parseError.value = "导入内容必须是 JSON 对象。";
      return null;
    }
    return parsed;
  } catch (error) {
    parseError.value = error instanceof Error ? error.message : "JSON 解析失败";
    return null;
  }
}

function downloadExportSnapshot() {
  if (!exportSnapshot.value) {
    return;
  }
  const blob = new Blob([JSON.stringify(exportSnapshot.value, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `parallellines-migration-${Date.now()}.json`;
  link.click();
  URL.revokeObjectURL(url);
}
</script>

<template>
  <UiCard class="admin-migration-tools-panel">
    <div class="panel-heading">
      <div>
        <h2>导入、导出与迁移工具</h2>
      </div>
      <button type="button" class="secondary-action" :disabled="exportLoading" @click="loadExport">
        {{ exportLoading ? "导出中..." : "生成导出快照" }}
      </button>
    </div>

    <div class="migration-grid">
      <label class="json-editor">
        <span>迁移 JSON</span>
        <textarea v-model="importJson" rows="15" spellcheck="false" />
      </label>

      <div class="migration-side">
        <div v-if="parseError" class="status-card is-error">{{ parseError }}</div>
        <div v-if="previewMutation.error.value" class="status-card is-error">
          {{ previewMutation.error.value.message }}
        </div>
        <div v-if="runMutation.error.value" class="status-card is-error">
          {{ runMutation.error.value.message }}
        </div>
        <div v-if="lastResult" class="status-card">
          <strong>{{ lastResult.dry_run ? "预检结果" : "导入结果" }}</strong>
          <span>
            新增 {{ lastResult.created }}，跳过 {{ lastResult.skipped }}，错误 {{ lastResult.errors }}
          </span>
        </div>

        <div class="migration-actions">
          <button type="button" :disabled="previewMutation.isPending.value" @click="previewImport">
            {{ previewMutation.isPending.value ? "预检中..." : "预检导入" }}
          </button>
          <button type="button" :disabled="runMutation.isPending.value" class="danger-action" @click="runImport">
            {{ runMutation.isPending.value ? "导入中..." : "执行导入" }}
          </button>
        </div>

        <ul v-if="resultRows.length" class="migration-rows">
          <li v-for="row in resultRows" :key="`${row.resource}-${row.key}-${row.action}`">
            <strong>{{ row.action }}</strong>
            <span>{{ row.resource }} · {{ row.key }} · {{ row.message }}</span>
          </li>
        </ul>
      </div>
    </div>

    <div v-if="exportError" class="status-card is-error">{{ exportError }}</div>
    <div v-if="exportSnapshot" class="export-summary">
      <span>快照时间：{{ exportSnapshot.exported_at }}</span>
      <span>用户 {{ exportSnapshot.users.length }}</span>
      <span>版块 {{ exportSnapshot.boards.length }}</span>
      <span>主题 {{ exportSnapshot.topics.length }}</span>
      <span>楼层 {{ exportSnapshot.posts.length }}</span>
      <button type="button" class="secondary-action" @click="downloadExportSnapshot">下载 JSON</button>
    </div>
  </UiCard>
</template>

<style scoped lang="scss" src="./AdminMigrationToolsPanel.scss"></style>
