<script setup lang="ts">
import {
  CheckOutlined,
  CopyOutlined,
  DeleteOutlined,
  HistoryOutlined,
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
  SendOutlined,
  SettingOutlined,
} from "@ant-design/icons-vue";
import { message as toast } from "ant-design-vue";
import { computed, ref, watch } from "vue";

import { ApiError } from "@/shared/api/client";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";
import UiEmptyState from "@/shared/ui/EmptyState.vue";

import { DAILY_REPORT_STYLE_OPTIONS } from "../model";
import type { DailyReportInput, DailyReportStyle } from "../model";
import {
  useAcceptDailyReportPreference,
  useClearDailyReportHistory,
  useConfirmDailyReportSession,
  useContinueDailyReportSession,
  useDailyReportHistory,
  useDailyReportProfile,
  useDailyReportSession,
  useDeleteDailyReport,
  useResetDailyReportProfile,
  useStartDailyReportSession,
  useUpdateDailyReportProfile,
} from "../queries";

const activeSessionId = ref("");
const workDate = ref(localDateValue());
const recurringWork = ref("");
const extraWork = ref("");
const risks = ref("");
const tomorrowPlan = ref("");
const style = ref<DailyReportStyle>("detailed");
const feedback = ref("");
const editableDraft = ref("");
const promptDraft = ref("");
const promptSettingsOpen = ref(false);
const confirmedSessionId = ref("");
const acceptedSuggestion = ref("");
const visibleError = ref("");

const profileQuery = useDailyReportProfile();
const historyQuery = useDailyReportHistory(30);
const sessionQuery = useDailyReportSession(activeSessionId);
const startSession = useStartDailyReportSession();
const continueSession = useContinueDailyReportSession();
const confirmSession = useConfirmDailyReportSession();
const updateProfile = useUpdateDailyReportProfile();
const resetProfile = useResetDailyReportProfile();
const acceptPreference = useAcceptDailyReportPreference();
const deleteReport = useDeleteDailyReport();
const clearHistory = useClearDailyReportHistory();

const profile = computed(() => profileQuery.data.value);
const session = computed(() => sessionQuery.data.value);
const history = computed(() => historyQuery.data.value ?? []);
const activeProviderMode = computed(
  () => session.value?.provider_mode ?? profile.value?.provider_mode ?? "local_fallback",
);
const activeModelName = computed(
  () => session.value?.model_name ?? profile.value?.model_name ?? "本地降级",
);
const isConfirmed = computed(
  () => session.value?.status === "confirmed" || confirmedSessionId.value === session.value?.id,
);
const latestPreferenceSuggestion = computed(() => {
  const messages = session.value?.messages ?? [];
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const suggestion = messages[index]?.preference_suggestion;
    if (suggestion && suggestion !== acceptedSuggestion.value) return suggestion;
  }
  return "";
});
const generationPending = computed(
  () => startSession.isPending.value || continueSession.isPending.value,
);

watch(
  () => session.value?.version,
  () => {
    if (session.value) editableDraft.value = session.value.current_draft;
  },
  { immediate: true },
);

watch(
  () => profile.value?.prompt_version,
  () => {
    if (profile.value) promptDraft.value = profile.value.custom_prompt;
  },
  { immediate: true },
);

async function generateReport(): Promise<void> {
  visibleError.value = "";
  const payload = currentInput();
  if (!payload.recurring_work.length && !payload.extra_work.length) {
    visibleError.value = "请至少填写一项真实的常规工作或今日额外工作。";
    return;
  }
  try {
    const result = await startSession.mutateAsync(payload);
    activeSessionId.value = result.id;
    editableDraft.value = result.current_draft;
    feedback.value = "";
    confirmedSessionId.value = "";
    acceptedSuggestion.value = "";
    toast.success("日报草稿已生成");
  } catch (error) {
    showError(error, "日报生成失败，请稍后重试");
  }
}

async function sendFeedback(): Promise<void> {
  const current = session.value;
  const text = feedback.value.trim();
  if (!current || !text || generationPending.value || isConfirmed.value) return;
  visibleError.value = "";
  try {
    const result = await continueSession.mutateAsync({
      sessionId: current.id,
      payload: {
        message: text,
        current_content: editableDraft.value.trim(),
        expected_version: current.version,
      },
    });
    feedback.value = "";
    editableDraft.value = result.current_draft;
    toast.success("已根据新要求更新");
  } catch (error) {
    showError(error, "修改失败，请稍后重试");
  }
}

async function confirmCurrentReport(): Promise<void> {
  const current = session.value;
  const content = editableDraft.value.trim();
  if (!current || !content || isConfirmed.value) return;
  try {
    await confirmSession.mutateAsync({
      sessionId: current.id,
      payload: { content, expected_version: current.version },
    });
    confirmedSessionId.value = current.id;
    toast.success("已保存到日报历史");
  } catch (error) {
    showError(error, "保存日报失败");
  }
}

async function copyText(content = editableDraft.value): Promise<void> {
  if (!content.trim()) return;
  try {
    await navigator.clipboard.writeText(content);
    toast.success("已复制日报");
  } catch {
    toast.error("复制失败，请手动选择文本复制");
  }
}

async function savePrompt(): Promise<void> {
  const current = profile.value;
  if (!current || !promptDraft.value.trim()) return;
  try {
    await updateProfile.mutateAsync({
      custom_prompt: promptDraft.value.trim(),
      expected_version: current.prompt_version,
    });
    toast.success("个人 Prompt 已保存");
  } catch (error) {
    showError(error, "Prompt 保存失败");
  }
}

async function restoreDefaultPrompt(): Promise<void> {
  if (!window.confirm("恢复默认 Prompt？已保存的日报不会删除。")) return;
  try {
    await resetProfile.mutateAsync();
    toast.success("已恢复默认 Prompt");
  } catch (error) {
    showError(error, "Prompt 恢复失败");
  }
}

async function saveSuggestedPreference(): Promise<void> {
  const current = profile.value;
  const suggestion = latestPreferenceSuggestion.value;
  if (!current || !suggestion) return;
  try {
    await acceptPreference.mutateAsync({
      requirement: suggestion,
      expected_version: current.prompt_version,
    });
    acceptedSuggestion.value = suggestion;
    toast.success("已加入你的长期写作偏好");
  } catch (error) {
    showError(error, "长期偏好保存失败");
  }
}

async function removeHistoryItem(reportId: string): Promise<void> {
  if (!window.confirm("删除这份历史日报？此操作不能撤销。")) return;
  try {
    await deleteReport.mutateAsync(reportId);
    toast.success("历史日报已删除");
  } catch (error) {
    showError(error, "删除失败");
  }
}

async function removeAllHistory(): Promise<void> {
  if (!window.confirm("清空全部日报历史和生成会话？个人 Prompt 会保留。")) return;
  try {
    await clearHistory.mutateAsync();
    activeSessionId.value = "";
    editableDraft.value = "";
    confirmedSessionId.value = "";
    toast.success("日报历史已清空");
  } catch (error) {
    showError(error, "清空失败");
  }
}

function currentInput(): DailyReportInput {
  return {
    work_date: workDate.value,
    recurring_work: splitItems(recurringWork.value),
    extra_work: splitItems(extraWork.value),
    risks: splitItems(risks.value),
    tomorrow_plan: splitItems(tomorrowPlan.value),
    style: style.value,
  };
}

function splitItems(value: string): string[] {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim().replace(/^[-*\d.、]+\s*/, ""))
    .filter(Boolean)
    .slice(0, 30);
}

function localDateValue(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function showError(error: unknown, fallback: string): void {
  const text = error instanceof ApiError || error instanceof Error ? error.message : fallback;
  visibleError.value = text || fallback;
  toast.error(visibleError.value);
}
</script>

<template>
  <section class="daily-report-workspace" aria-labelledby="daily-report-title">
    <header class="daily-report-workspace__header">
      <div>
        <span class="daily-report-workspace__eyebrow">社区工具箱</span>
        <h1 id="daily-report-title">个人日报助手</h1>
        <p>记录真实工作，多轮调整表达，并逐步形成只属于你的日报 Prompt。</p>
      </div>
      <span v-if="profile" class="daily-report-workspace__mode" :class="{ 'is-fallback': activeProviderMode === 'local_fallback' }">
        <RobotOutlined aria-hidden="true" />
        {{ activeProviderMode === "ai" ? activeModelName : "本地降级" }}
      </span>
    </header>

    <p v-if="profile" class="daily-report-workspace__privacy">{{ profile.privacy_notice }}</p>
    <p v-if="profileQuery.isLoading.value" class="daily-report-state" role="status">正在加载个人设置…</p>
    <p v-else-if="profileQuery.isError.value" class="daily-report-state is-error" role="alert">个人设置加载失败，请刷新页面重试。</p>
    <p v-if="visibleError" class="daily-report-state is-error" role="alert">{{ visibleError }}</p>

    <div class="daily-report-workspace__grid">
      <UiCard>
        <form class="daily-report-form" @submit.prevent="generateReport">
          <div class="daily-report-form__heading">
            <div><span>01</span><h2>填写今天的真实工作</h2></div>
            <small>每行一项，重复工作也可以照常填写</small>
          </div>
          <div class="daily-report-form__row">
            <label><span>工作日期</span><input v-model="workDate" type="date" required /></label>
            <label>
              <span>表达风格</span>
              <select v-model="style">
                <option v-for="option in DAILY_REPORT_STYLE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>
          </div>
          <label><span>常规工作</span><textarea v-model="recurringWork" rows="5" placeholder="例：处理用户反馈&#10;检查线上服务状态&#10;跟进需求排期"></textarea></label>
          <label><span>今日额外工作</span><textarea v-model="extraWork" rows="3" placeholder="例：排查登录异常并完成修复验证"></textarea></label>
          <label><span>问题风险（可选）</span><textarea v-model="risks" rows="2" placeholder="没有内容时会自动隐藏这一段"></textarea></label>
          <label><span>明日计划（可选）</span><textarea v-model="tomorrowPlan" rows="3" placeholder="例：继续跟进灰度反馈"></textarea></label>
          <UiButton type="submit" tone="primary" :disabled="startSession.isPending.value">
            <template #icon><RobotOutlined aria-hidden="true" /></template>
            {{ startSession.isPending.value ? "正在生成…" : "生成日报" }}
          </UiButton>
        </form>
      </UiCard>

      <UiCard>
        <section class="daily-report-result" aria-labelledby="daily-report-result-title">
          <div class="daily-report-form__heading">
            <div><span>02</span><h2 id="daily-report-result-title">调整并确认</h2></div>
            <small v-if="session">Prompt v{{ session.prompt_version }} · 草稿 v{{ session.version }}</small>
          </div>
          <UiEmptyState v-if="!session" title="还没有日报草稿" description="填写左侧真实工作后生成第一版。" />
          <template v-else>
            <textarea v-model="editableDraft" class="daily-report-result__editor" aria-label="可编辑日报正文" rows="18" :disabled="isConfirmed"></textarea>
            <div class="daily-report-result__actions">
              <UiButton tone="subtle" @click="copyText()"><template #icon><CopyOutlined aria-hidden="true" /></template>复制</UiButton>
              <UiButton tone="success" :disabled="isConfirmed || confirmSession.isPending.value" @click="confirmCurrentReport">
                <template #icon><CheckOutlined aria-hidden="true" /></template>{{ isConfirmed ? "已保存" : "确认并存入历史" }}
              </UiButton>
            </div>
            <ol class="daily-report-conversation" aria-label="日报调整对话">
              <li v-for="item in session.messages" :key="item.id" :class="`is-${item.role}`">
                <strong>{{ item.role === "user" ? "你" : "日报助手" }}</strong><p>{{ item.content }}</p>
              </li>
            </ol>
            <aside v-if="latestPreferenceSuggestion" class="daily-report-suggestion">
              <div><strong>发现一条可能长期有效的偏好</strong><p>{{ latestPreferenceSuggestion }}</p></div>
              <UiButton tone="subtle" :disabled="acceptPreference.isPending.value" @click="saveSuggestedPreference">
                <template #icon><SaveOutlined aria-hidden="true" /></template>保存为长期偏好
              </UiButton>
            </aside>
            <form class="daily-report-followup" @submit.prevent="sendFeedback">
              <label for="daily-report-feedback">继续告诉助手哪里需要改</label>
              <div>
                <textarea id="daily-report-feedback" v-model="feedback" rows="2" :disabled="isConfirmed" placeholder="例：再自然一点，少用“推进”；这条要求以后都要遵守"></textarea>
                <UiButton type="submit" tone="primary" :disabled="!feedback.trim() || generationPending || isConfirmed">
                  <template #icon><SendOutlined aria-hidden="true" /></template>{{ continueSession.isPending.value ? "修改中…" : "发送" }}
                </UiButton>
              </div>
            </form>
          </template>
        </section>
      </UiCard>
    </div>

    <UiCard v-if="profile">
      <section class="daily-report-settings">
        <button class="daily-report-settings__toggle" type="button" :aria-expanded="promptSettingsOpen" aria-controls="daily-report-prompt-settings" @click="promptSettingsOpen = !promptSettingsOpen">
          <span><SettingOutlined aria-hidden="true" /> 我的定制 Prompt</span><small>当前版本 v{{ profile.prompt_version }}</small>
        </button>
        <div v-if="promptSettingsOpen" id="daily-report-prompt-settings" class="daily-report-settings__body">
          <p>这里只保存你的表达偏好；站点的真实性和格式约束不会被覆盖。</p>
          <textarea v-model="promptDraft" rows="7" aria-label="个人日报 Prompt"></textarea>
          <div>
            <UiButton tone="primary" :disabled="updateProfile.isPending.value" @click="savePrompt"><template #icon><SaveOutlined aria-hidden="true" /></template>保存 Prompt</UiButton>
            <UiButton tone="ghost" :disabled="resetProfile.isPending.value" @click="restoreDefaultPrompt"><template #icon><ReloadOutlined aria-hidden="true" /></template>恢复默认</UiButton>
          </div>
        </div>
      </section>
    </UiCard>

    <UiCard>
      <section class="daily-report-history" aria-labelledby="daily-report-history-title">
        <div class="daily-report-history__header">
          <div><HistoryOutlined aria-hidden="true" /><h2 id="daily-report-history-title">历史日报</h2><span>{{ history.length }} 份</span></div>
          <UiButton v-if="history.length" tone="danger" @click="removeAllHistory"><template #icon><DeleteOutlined aria-hidden="true" /></template>清空</UiButton>
        </div>
        <p v-if="historyQuery.isLoading.value" class="daily-report-state" role="status">正在加载历史…</p>
        <p v-else-if="historyQuery.isError.value" class="daily-report-state is-error" role="alert">历史日报加载失败。</p>
        <UiEmptyState v-else-if="!history.length" title="暂无历史日报" description="确认后的日报会出现在这里，并用于后续降低重复率。" />
        <div v-else class="daily-report-history__list">
          <details v-for="record in history" :key="record.id">
            <summary><span><strong>{{ record.work_date }}</strong><small>Prompt v{{ record.prompt_version }} · {{ record.model_name }}</small></span><span>查看正文</span></summary>
            <pre>{{ record.content }}</pre>
            <div>
              <UiButton tone="subtle" @click="copyText(record.content)"><template #icon><CopyOutlined aria-hidden="true" /></template>复制</UiButton>
              <UiButton tone="danger" @click="removeHistoryItem(record.id)"><template #icon><DeleteOutlined aria-hidden="true" /></template>删除</UiButton>
            </div>
          </details>
        </div>
      </section>
    </UiCard>
  </section>
</template>

<style scoped lang="scss" src="./DailyReportWorkspace.scss"></style>
