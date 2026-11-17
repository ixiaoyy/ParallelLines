<script setup lang="ts">
import { builtinSiteText, currentLocale, uiText } from "@/shared/i18n/locale";
import { computed, ref } from "vue";

import {
  formatCentsToYuan,
  getLedgerCategoryMeta,
  type JournalVisibility,
  type SpaceLedgerItem,
  type SpaceLedgerMonthlySummary,
} from "@/features/space/model";
import UiButton from "@/shared/ui/Button.vue";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  selectedMonth: string;
  ledgerSummary?: SpaceLedgerMonthlySummary;
  ledgers: SpaceLedgerItem[];
  budgetUsagePercent: number;
  remainingBudgetCents: number;
}>();

const emit = defineEmits<{
  shareMonthlyBill: [visibility: JournalVisibility, hideExactAmount: boolean];
  deleteLedger: [item: SpaceLedgerItem];
  composeLedger: [];
}>();

const hideExactAmountOnShare = ref(true);

const monthLedgersGrouped = computed(() => {
  const prefix = `${props.selectedMonth}-`;
  const list = props.ledgers.filter((item) => item.entry_date.startsWith(prefix));
  const groups = new Map<
    string,
    { date: string; items: SpaceLedgerItem[]; dayExpense: number; dayIncome: number }
  >();
  for (const item of list) {
    const group = groups.get(item.entry_date) ?? {
      date: item.entry_date,
      items: [],
      dayExpense: 0,
      dayIncome: 0,
    };
    group.items.push(item);
    if (item.kind === "income") {
      group.dayIncome += item.amount_cents;
    } else {
      group.dayExpense += item.amount_cents;
    }
    groups.set(item.entry_date, group);
  }
  return Array.from(groups.values());
});

const monthlyLifestylePortrait = computed(() => {
  const summary = props.ledgerSummary;
  if (!summary || summary.entry_count === 0) return "";
  const parts: string[] = [];
  const top = summary.category_breakdown[0];
  if (top) {
    const meta = getLedgerCategoryMeta(top.category);
    parts.push(uiText("{emoji} {category}占 {percent}%", { emoji: meta.emoji, category: uiText(meta.label), percent: top.ratio_percent }));
  }
  const coffee = summary.category_breakdown.find((c) => c.category === "coffee");
  if (coffee && coffee.count > 0) {
    parts.push(uiText("☕ 咖啡饮品 {count} 笔", { count: coffee.count }));
  }
  parts.push(uiText("共记 {count} 笔", { count: summary.entry_count }));
  if (summary.monthly_budget_cents > 0) {
    const remain = summary.monthly_budget_cents - summary.total_expense_cents;
    parts.push(uiText(remain >= 0 ? "未超出本月预算" : "已超出本月预算"));
  }
  return parts.join(" · ");
});
</script>

<template>
  <section class="space-ledger-section" :aria-label="uiText('私人记账本')">
    <UiCard v-if="ledgerSummary" class="ledger-overview-card">
      <div class="ledger-overview-card__head">
        <div>
          <span class="kicker">{{ uiText('🔒 私人月度账本（仅自己可见）') }}</span>
          <h2>{{ uiText('{month} 收支总览', { month: selectedMonth }) }}</h2>
          <p v-if="monthlyLifestylePortrait" class="ledger-portrait-line">
            ✨ {{ monthlyLifestylePortrait }}
          </p>
        </div>
        <div class="ledger-share-box">
          <label class="hide-amount-check">
            <input v-model="hideExactAmountOnShare" type="checkbox" />
            <span>{{ uiText('仅晒比例（隐藏金额）') }}</span>
          </label>
          <UiButton
            type="button"
            tone="subtle"
            :disabled="ledgerSummary.entry_count === 0"
            @click="emit('shareMonthlyBill', 'private', hideExactAmountOnShare)"
          >
            {{ uiText('预览月度小结') }}
          </UiButton>
        </div>
      </div>

      <div class="ledger-metrics-grid">
        <div class="metric-item">
          <span>{{ uiText('本月支出') }}</span>
          <strong class="is-expense">
            {{ formatCentsToYuan(ledgerSummary.total_expense_cents) }}
          </strong>
        </div>
        <div class="metric-item">
          <span>{{ uiText('本月收入') }}</span>
          <strong class="is-income">
            {{ formatCentsToYuan(ledgerSummary.total_income_cents, true) }}
          </strong>
        </div>
        <div class="metric-item">
          <span>{{ uiText('预算剩余') }}</span>
          <strong :class="{ 'is-over': ledgerSummary.monthly_budget_cents > 0 && remainingBudgetCents < 0 }">
            {{ ledgerSummary.monthly_budget_cents > 0 ? formatCentsToYuan(remainingBudgetCents) : uiText('未设置') }}
          </strong>
        </div>
      </div>

      <!-- 预算为 0 时表示未设置，不把真实支出展示成超支。 -->
      <div v-if="ledgerSummary.monthly_budget_cents > 0" class="budget-progress-wrap">
        <div class="budget-progress-labels">
          <span>
            {{ uiText('月度预算进度（预算 {amount}）', { amount: formatCentsToYuan(ledgerSummary.monthly_budget_cents) }) }}
          </span>
          <b>{{ uiText('已用 {percent}%', { percent: budgetUsagePercent }) }}</b>
        </div>
        <div class="budget-progress-bar">
          <i
            :style="{ width: `${budgetUsagePercent}%` }"
            :class="{ 'is-warn': budgetUsagePercent >= 85 }"
          ></i>
        </div>
      </div>

      <div v-if="ledgerSummary.category_breakdown.length" class="ledger-breakdown-list">
        <h3>{{ uiText('支出分类占比') }}</h3>
        <div
          v-for="cat in ledgerSummary.category_breakdown"
          :key="cat.category"
          class="breakdown-row"
        >
          <span class="cat-badge">
            <em>{{ getLedgerCategoryMeta(cat.category).emoji }}</em>
            <b>{{ uiText(getLedgerCategoryMeta(cat.category).label) }}</b>
            <small>{{ uiText(cat.count === 1 ? builtinSiteText('space.entry_one', '{count} 笔', currentLocale) : '{count} 笔', { count: cat.count }) }}</small>
          </span>
          <div class="cat-track">
            <i
              :style="{
                width: `${Math.max(5, cat.ratio_percent)}%`,
                backgroundColor: getLedgerCategoryMeta(cat.category).color,
              }"
            ></i>
          </div>
          <span class="cat-amount">
            {{ formatCentsToYuan(cat.amount_cents) }} ({{ cat.ratio_percent }}%)
          </span>
        </div>
      </div>
    </UiCard>

    <div v-if="monthLedgersGrouped.length" class="ledger-day-groups">
      <UiCard v-for="group in monthLedgersGrouped" :key="group.date" class="ledger-day-card">
        <header class="ledger-day-card__head">
          <strong>📅 {{ group.date }}</strong>
          <div class="day-sums">
            <span v-if="group.dayExpense">{{ uiText('支') }} {{ formatCentsToYuan(group.dayExpense) }}</span>
            <span v-if="group.dayIncome" class="is-income">
              {{ uiText('收') }} {{ formatCentsToYuan(group.dayIncome, true) }}
            </span>
          </div>
        </header>

        <ul class="ledger-entry-list">
          <li v-for="item in group.items" :key="item.id" class="ledger-entry-row">
            <span
              class="entry-cat-icon"
              :style="{
                backgroundColor: getLedgerCategoryMeta(item.category).softBg,
                color: getLedgerCategoryMeta(item.category).color,
              }"
            >
              {{ getLedgerCategoryMeta(item.category).emoji }}
            </span>
            <div class="entry-info">
              <strong>{{ uiText(getLedgerCategoryMeta(item.category).label) }}</strong>
              <p>{{ item.note || uiText('无备注') }}</p>
            </div>
            <div class="entry-right">
              <b :class="item.kind === 'income' ? 'is-income' : 'is-expense'">
                {{
                  formatCentsToYuan(
                    item.kind === "income" ? item.amount_cents : -item.amount_cents,
                    true,
                  )
                }}
              </b>
              <button
                type="button"
                class="entry-del-btn"
                :title="uiText('删除此笔记录')"
                @click="emit('deleteLedger', item)"
              >
                {{ uiText('删除') }}
              </button>
            </div>
          </li>
        </ul>
      </UiCard>
    </div>

    <UiCard v-else class="space-empty-card">
      <span class="empty-emoji">🪙</span>
      <strong>{{ uiText('{month} 还没有记账流水', { month: selectedMonth }) }}</strong>
      <p>{{ uiText('使用上方「随手记一笔账」记录日常咖啡、餐饮或游戏开销，月底可一键生成漂亮的手账小结卡。') }}</p>
      <UiButton type="button" tone="primary" @click="emit('composeLedger')">
        {{ uiText('记第一笔账') }}
      </UiButton>
    </UiCard>
  </section>
</template>

<style scoped lang="scss">
.space-ledger-section {
  display: grid;
  gap: 0.9rem;
  min-width: 0;
}

.space-empty-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 2.4rem 1.2rem;
  text-align: center;
  color: var(--muted);

  .empty-emoji { font-size: 2.3rem; }
  strong { color: var(--title); font-size: 1rem; }
  p { margin: 0; max-width: 26rem; font-size: 0.86rem; line-height: 1.6; }
}

.ledger-overview-card {
  display: grid;
  gap: 1rem;
  padding: 1.15rem 1.2rem;
  border-radius: 1.35rem;
  border: 1px solid rgba(255, 255, 255, 0.88);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(14px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 10px 28px rgba(15, 23, 42, 0.05);

  &__head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: 0.7rem;

    .kicker { font-size: 0.74rem; font-weight: 800; color: var(--muted); }
    h2 { margin: 0.15rem 0 0; font-size: 1.15rem; font-weight: 900; color: var(--title); }
    .ledger-portrait-line {
      margin: 0.3rem 0 0;
      font-size: 0.8rem;
      font-weight: 700;
      color: var(--primary);
    }
  }
}

.ledger-share-box {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}

.hide-amount-check {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  font-weight: 700;
  color: var(--text);
  cursor: pointer;
}

.ledger-metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.6rem;
}

.metric-item {
  display: grid;
  gap: 0.2rem;
  padding: 0.75rem 0.85rem;
  border-radius: 0.95rem;
  background: var(--bg-subtle);

  span { font-size: 0.74rem; font-weight: 700; color: var(--muted); }

  strong {
    font-size: 1.2rem;
    font-weight: 900;
    color: var(--title);
    font-variant-numeric: tabular-nums;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.is-expense { color: #ea580c !important; }
.is-income { color: #10b981 !important; }
.is-over { color: #ef4444 !important; }

.budget-progress-wrap { display: grid; gap: 0.4rem; }

.budget-progress-labels {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.76rem;
  color: var(--muted);

  b { color: var(--title); }
}

.budget-progress-bar {
  height: 0.6rem;
  border-radius: 999px;
  background: var(--bg-subtle);
  overflow: hidden;

  i {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #66d4cb, #409eff);
    transition: width 400ms ease;

    &.is-warn { background: linear-gradient(90deg, #fbbf24, #f97316); }
  }
}

.ledger-breakdown-list {
  display: grid;
  gap: 0.5rem;

  h3 { margin: 0; font-size: 0.84rem; font-weight: 800; color: var(--title); }
}

.breakdown-row {
  display: grid;
  grid-template-columns: 8.5rem minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.8rem;
}

.cat-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  min-width: 0;

  em { font-style: normal; }
  b { font-weight: 800; color: var(--title); white-space: nowrap; }
  small { color: var(--muted); }
}

.cat-track {
  height: 0.5rem;
  border-radius: 999px;
  background: var(--bg-subtle);
  overflow: hidden;

  i { display: block; height: 100%; border-radius: 999px; }
}

.cat-amount {
  color: var(--text);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.ledger-day-groups { display: grid; gap: 0.75rem; }

.ledger-day-card {
  padding: 0.85rem 1rem;
  border-radius: 1.15rem;
  border: 1px solid rgba(255, 255, 255, 0.88);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(12px);
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.04);

  &__head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 0.5rem;
    border-bottom: 1px dashed var(--border);
    font-size: 0.84rem;

    strong { color: var(--title); }
  }
}

.day-sums {
  display: flex;
  gap: 0.6rem;
  font-size: 0.76rem;
  font-weight: 700;
  color: var(--muted);
}

.ledger-entry-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.ledger-entry-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.7rem;
  padding: 0.6rem 0;

  & + & { border-top: 1px solid var(--bg-subtle); }
}

.entry-cat-icon {
  display: grid;
  place-items: center;
  width: 2.3rem;
  height: 2.3rem;
  border-radius: 0.75rem;
  font-size: 1.1rem;
}

.entry-info {
  min-width: 0;

  strong { font-size: 0.86rem; color: var(--title); }

  p {
    margin: 0.1rem 0 0;
    font-size: 0.76rem;
    color: var(--muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.entry-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 0.1rem;

  b { font-size: 0.95rem; font-weight: 900; font-variant-numeric: tabular-nums; }
}

.entry-del-btn {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 0.7rem;
  cursor: pointer;
  opacity: 0.7;

  &:hover { color: var(--danger); opacity: 1; }
}

@media (max-width: 760px) {
  .ledger-metrics-grid { grid-template-columns: 1fr; }
  .breakdown-row { grid-template-columns: 7rem minmax(0, 1fr) auto; }
}
</style>
