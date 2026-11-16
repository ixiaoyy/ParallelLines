<script setup lang="ts">
import { reactive, watch } from "vue";

import { SPACE_COVER_PRESETS, type SpaceCoverPreset } from "@/features/space/model";
import UiButton from "@/shared/ui/Button.vue";

const props = withDefaults(
  defineProps<{
    spaceTitle: string;
    spaceSubtitle: string;
    coverPreset: SpaceCoverPreset;
    monthlyBudgetYuan: string;
    saving?: boolean;
  }>(),
  {
    saving: false,
  },
);

const emit = defineEmits<{
  save: [
    payload: {
      space_title: string;
      space_subtitle: string;
      cover_preset: SpaceCoverPreset;
      monthly_budget_cents: number;
    },
  ];
  close: [];
}>();

const draft = reactive({
  space_title: props.spaceTitle,
  space_subtitle: props.spaceSubtitle,
  cover_preset: props.coverPreset,
  monthlyBudgetYuan: props.monthlyBudgetYuan,
});

watch(
  () => [props.spaceTitle, props.spaceSubtitle, props.coverPreset, props.monthlyBudgetYuan] as const,
  ([title, subtitle, preset, budget]) => {
    draft.space_title = title;
    draft.space_subtitle = subtitle;
    draft.cover_preset = preset;
    draft.monthlyBudgetYuan = budget;
  },
);

function handleSave() {
  const budgetYuan = Number.parseFloat(draft.monthlyBudgetYuan);
  const budgetCents =
    Number.isFinite(budgetYuan) && budgetYuan >= 0 ? Math.round(budgetYuan * 100) : 300000;
  emit("save", {
    space_title: draft.space_title.trim(),
    space_subtitle: draft.space_subtitle.trim(),
    cover_preset: draft.cover_preset,
    monthly_budget_cents: budgetCents,
  });
}
</script>

<template>
  <div class="space-settings-drawer">
    <div class="space-settings-drawer__grid">
      <label>
        <span>空间名称</span>
        <input
          v-model="draft.space_title"
          type="text"
          maxlength="80"
          placeholder="例如：阿星的光年手账本"
        />
      </label>
      <label>
        <span>空间签名 / 寄语</span>
        <input
          v-model="draft.space_subtitle"
          type="text"
          maxlength="200"
          placeholder="写一句展示在空间顶部的生活寄语…"
        />
      </label>
      <label>
        <span>每月记账预算（元，仅自己可见）</span>
        <input
          v-model="draft.monthlyBudgetYuan"
          type="number"
          min="0"
          step="100"
          placeholder="3000"
        />
      </label>
    </div>

    <div class="space-settings-drawer__presets">
      <span>封面视觉主题：</span>
      <div class="preset-pills">
        <button
          v-for="preset in SPACE_COVER_PRESETS"
          :key="preset.key"
          type="button"
          :class="{ active: draft.cover_preset === preset.key }"
          @click="draft.cover_preset = preset.key"
        >
          {{ preset.label }}
        </button>
      </div>
    </div>

    <div class="space-settings-drawer__footer">
      <UiButton type="button" tone="primary" :loading="saving" @click="handleSave">
        保存空间设置
      </UiButton>
      <UiButton type="button" tone="ghost" @click="emit('close')">
        收起
      </UiButton>
    </div>
  </div>
</template>

<style scoped lang="scss">
.space-settings-drawer {
  position: relative;
  display: grid;
  gap: 0.9rem;
  margin: 0 1rem 1rem;
  padding: 1rem 1.1rem;
  border-radius: 1.1rem;
  background: rgba(255, 255, 255, 0.92);
  color: var(--text);
  box-shadow: var(--shadow-card);

  &__grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;

    label {
      display: grid;
      gap: 0.3rem;
      font-size: 0.78rem;
      font-weight: 700;
      color: var(--muted);
    }

    input {
      width: 100%;
      padding: 0.55rem 0.75rem;
      border-radius: 0.75rem;
      border: 1px solid var(--border);
      background: var(--bg-surface);
      color: var(--title);
      font-size: 0.88rem;
      outline: none;
      transition: border-color 0.16s ease, box-shadow 0.16s ease;

      &:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 3px rgba(64, 158, 255, 0.14);
      }
    }
  }

  &__presets {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    font-weight: 700;
  }

  &__footer {
    display: flex;
    gap: 0.5rem;
  }
}

.preset-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;

  button {
    padding: 0.3rem 0.75rem;
    border-radius: var(--radius-pill);
    border: 1px solid var(--border);
    background: var(--bg-surface);
    color: var(--text);
    font-size: 0.78rem;
    font-weight: 700;
    cursor: pointer;

    &.active {
      border-color: var(--theme-soft-border, rgba(64, 158, 255, 0.4));
      background: var(--theme-soft-bg, rgba(64, 158, 255, 0.12));
      color: var(--primary);
    }
  }
}

@media (max-width: 760px) {
  .space-settings-drawer__grid {
    grid-template-columns: 1fr;
  }
}
</style>
