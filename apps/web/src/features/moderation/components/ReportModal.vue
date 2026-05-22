<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { FlagReason, FlagTargetType } from "../model";
import { useCreateFlag } from "../queries";
import UiButton from "@/shared/ui/Button.vue";

const props = defineProps<{
  open: boolean;
  targetType: FlagTargetType;
  targetId: string;
}>();

const emit = defineEmits<{
  close: [];
  success: [];
}>();

const reason = ref<FlagReason>("spam");
const detail = ref("");
const statusMessage = ref("");
const statusTone = ref<"success" | "danger" | "">("");

const createFlagMutation = useCreateFlag();
const isPending = computed(() => createFlagMutation.isPending.value);

// Reset state when opening/closing
watch(
  () => props.open,
  (newOpen) => {
    if (newOpen) {
      reason.value = "spam";
      detail.value = "";
      statusMessage.value = "";
      statusTone.value = "";
    }
  },
);

function handleClose() {
  if (isPending.value) {
    return;
  }
  emit("close");
}

function handleSubmit() {
  if (isPending.value) {
    return;
  }

  createFlagMutation.mutate(
    {
      target_type: props.targetType,
      target_id: props.targetId,
      reason: reason.value,
      detail: detail.value.trim() || null,
    },
    {
      onSuccess: () => {
        statusTone.value = "success";
        statusMessage.value = "举报提交成功，感谢您的反馈！";
        window.setTimeout(() => {
          emit("success");
          emit("close");
        }, 1500);
      },
      onError: (error: unknown) => {
        statusTone.value = "danger";
        // Check for specific duplicate flags error
        const err = error as { response?: { data?: { detail?: string } }; message?: string };
        const errorDetail = err.response?.data?.detail ?? err.message ?? "";
        if (
          errorDetail.includes("already flagged") ||
          errorDetail.includes("duplicate") ||
          errorDetail.includes("conflict")
        ) {
          statusMessage.value = "您已经举报过该内容，请勿重复提交。";
        } else {
          statusMessage.value = err.message || "提交举报失败，请稍后重试。";
        }
      },
    },
  );
}
</script>

<template>
  <div
    class="report-modal-overlay"
    :class="{ 'report-modal-overlay--open': open }"
    @click="handleClose"
    role="dialog"
    aria-modal="true"
    aria-labelledby="report-modal-title"
  >
    <div class="report-modal-panel" :class="{ 'report-modal-panel--open': open }" @click.stop>
      <header class="report-modal-header">
        <h3 id="report-modal-title">举报违规内容</h3>
        <button class="close-btn" :disabled="isPending" @click="handleClose" aria-label="关闭">&times;</button>
      </header>

      <div class="report-modal-body">
        <span class="section-kicker">请选择举报原因</span>
        <div class="reason-options">
          <label class="reason-option" :class="{ selected: reason === 'spam' }">
            <input type="radio" v-model="reason" value="spam" :disabled="isPending" />
            <div class="option-card">
              <strong>垃圾广告 / 刷屏</strong>
              <span>发布推广、诈骗、重复刷屏或无意义灌水内容</span>
            </div>
          </label>

          <label class="reason-option" :class="{ selected: reason === 'harassment' }">
            <input type="radio" v-model="reason" value="harassment" :disabled="isPending" />
            <div class="option-card">
              <strong>骚扰攻击</strong>
              <span>侮辱谩骂、人身攻击、恶意挑衅或仇恨性言论</span>
            </div>
          </label>

          <label class="reason-option" :class="{ selected: reason === 'off_topic' }">
            <input type="radio" v-model="reason" value="off_topic" :disabled="isPending" />
            <div class="option-card">
              <strong>无关内容</strong>
              <span>发表与当前主题或版块讨论完全无关的内容</span>
            </div>
          </label>

          <label class="reason-option" :class="{ selected: reason === 'private_info' }">
            <input type="radio" v-model="reason" value="private_info" :disabled="isPending" />
            <div class="option-card">
              <strong>泄露隐私</strong>
              <span>发布他人姓名、身份证号、电话、地址等隐私敏感信息</span>
            </div>
          </label>

          <label class="reason-option" :class="{ selected: reason === 'other' }">
            <input type="radio" v-model="reason" value="other" :disabled="isPending" />
            <div class="option-card">
              <strong>其他违规</strong>
              <span>其他违反社区准则的行为（请在下方写明详情）</span>
            </div>
          </label>
        </div>

        <div class="detail-section">
          <label class="detail-label">
            <span>补充详情描述（可选）</span>
            <textarea
              v-model="detail"
              rows="3"
              maxlength="500"
              placeholder="请输入补充信息，帮助审核人员更快更准确地做出判断..."
              :disabled="isPending"
            />
          </label>
        </div>

        <transition name="fade">
          <div v-if="statusMessage" class="status-alert" :class="`status-alert--${statusTone}`" role="status">
            {{ statusMessage }}
          </div>
        </transition>
      </div>

      <footer class="report-modal-footer">
        <UiButton tone="ghost" :disabled="isPending" @click="handleClose">取消</UiButton>
        <UiButton tone="primary" :disabled="isPending" @click="handleSubmit">
          {{ isPending ? "提交中…" : "提交举报" }}
        </UiButton>
      </footer>
    </div>
  </div>
</template>

<style scoped lang="scss" src="./ReportModal.scss"></style>
