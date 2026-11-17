<script setup lang="ts">
import { uiText } from "@/shared/i18n/locale";
import { computed } from "vue";

import {
  formatCentsToYuan,
  getLedgerCategoryMeta,
  getMoodMeta,
  getWeatherMeta,
  type SpaceJournalItem,
  type SpaceLedgerItem,
} from "@/features/space/model";
import UiButton from "@/shared/ui/Button.vue";

const props = defineProps<{
  date: string;
  journals: SpaceJournalItem[];
  ledgers: SpaceLedgerItem[];
}>();

const emit = defineEmits<{
  close: [];
  filterByDate: [date: string];
  writeForDate: [date: string];
}>();

const dayJournals = computed(() => props.journals.filter((j) => j.entry_date === props.date));
const dayLedgers = computed(() => props.ledgers.filter((l) => l.entry_date === props.date));

const dayTotals = computed(() => {
  let expense = 0;
  let income = 0;
  for (const item of dayLedgers.value) {
    if (item.kind === "income") income += item.amount_cents;
    else expense += item.amount_cents;
  }
  return { expense, income };
});
</script>

<template>
  <div class="slice-modal-backdrop" role="dialog" aria-modal="true" :aria-label="uiText('一日生活切片')" @click.self="emit('close')">
    <div class="slice-modal-card">
      <header class="slice-modal-head">
        <div>
          <span class="slice-kicker">{{ uiText('🗓️ 一日生活切片') }}</span>
          <h3>{{ date }}</h3>
        </div>
        <button type="button" class="slice-close-btn" :aria-label="uiText('关闭')" @click="emit('close')">
          ×
        </button>
      </header>

      <div class="slice-modal-body">
        <section class="slice-section">
          <h4>{{ uiText('📖 当日手账（{count}）', { count: dayJournals.length }) }}</h4>
          <div v-if="dayJournals.length" class="slice-journal-list">
            <article v-for="j in dayJournals" :key="j.id" class="slice-journal-item">
              <div class="slice-journal-meta">
                <span v-if="j.mood">{{ getMoodMeta(j.mood).emoji }} {{ uiText(getMoodMeta(j.mood).label) }}</span>
                <span v-if="j.weather">{{ getWeatherMeta(j.weather).emoji }} {{ uiText(getWeatherMeta(j.weather).label) }}</span>
                <span v-if="j.location">📍 {{ j.location }}</span>
              </div>
              <p v-if="j.is_locked" class="slice-locked-note">
                {{ uiText('💌 封存中的时间胶囊（将于 {date} 拆封）', { date: j.unlock_at ?? '' }) }}
              </p>
              <template v-else>
                <strong v-if="j.title">{{ j.title }}</strong>
                <p>{{ j.content }}</p>
              </template>
            </article>
          </div>
          <p v-else class="slice-empty-hint">{{ uiText('这一天还没有留下手账记录。') }}</p>
        </section>

        <section class="slice-section">
          <div class="slice-section-head">
            <h4>{{ uiText('💰 当日收支（{count}）', { count: dayLedgers.length }) }}</h4>
            <div v-if="dayLedgers.length" class="slice-day-sums">
              <span v-if="dayTotals.expense" class="is-expense">
                {{ uiText('支') }} {{ formatCentsToYuan(dayTotals.expense) }}
              </span>
              <span v-if="dayTotals.income" class="is-income">
                {{ uiText('收') }} {{ formatCentsToYuan(dayTotals.income, true) }}
              </span>
            </div>
          </div>

          <ul v-if="dayLedgers.length" class="slice-ledger-list">
            <li v-for="l in dayLedgers" :key="l.id">
              <span>
                {{ getLedgerCategoryMeta(l.category).emoji }}
                {{ l.note || uiText(getLedgerCategoryMeta(l.category).label) }}
              </span>
              <b :class="l.kind === 'income' ? 'is-income' : 'is-expense'">
                {{ formatCentsToYuan(l.kind === "income" ? l.amount_cents : -l.amount_cents, true) }}
              </b>
            </li>
          </ul>
          <p v-else class="slice-empty-hint">{{ uiText('这一天没有记账流水。') }}</p>
        </section>
      </div>

      <footer class="slice-modal-footer">
        <UiButton type="button" tone="subtle" @click="emit('filterByDate', date)">
          {{ uiText('在时间线查看这一天') }}
        </UiButton>
        <UiButton type="button" tone="primary" @click="emit('writeForDate', date)">
          {{ uiText('✍️ 补记这一天') }}
        </UiButton>
      </footer>
    </div>
  </div>
</template>

<style scoped lang="scss">
.slice-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  padding: 1rem;
  background: rgba(15, 23, 42, 0.35);
  backdrop-filter: blur(6px);
}

.slice-modal-card {
  display: grid;
  gap: 1rem;
  width: min(32rem, 100%);
  max-height: 82vh;
  overflow-y: auto;
  padding: 1.25rem;
  border-radius: 1.4rem;
  border: 1px solid rgba(255, 255, 255, 0.9);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(18px);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.2);
}

.slice-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;

  .slice-kicker {
    font-size: 0.74rem;
    font-weight: 800;
    color: var(--primary);
  }

  h3 {
    margin: 0.15rem 0 0;
    font-size: 1.25rem;
    font-weight: 900;
    color: var(--title);
  }
}

.slice-close-btn {
  width: 2rem;
  height: 2rem;
  border: 0;
  border-radius: 50%;
  background: var(--bg-subtle);
  color: var(--text);
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

.slice-modal-body {
  display: grid;
  gap: 0.95rem;
}

.slice-section {
  display: grid;
  gap: 0.5rem;
  padding: 0.85rem;
  border-radius: 1rem;
  background: var(--bg-subtle);

  h4 {
    margin: 0;
    font-size: 0.84rem;
    font-weight: 800;
    color: var(--title);
  }
}

.slice-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.slice-day-sums {
  display: flex;
  gap: 0.5rem;
  font-size: 0.78rem;
  font-weight: 800;
}

.is-expense { color: #ea580c; }
.is-income { color: #10b981; }

.slice-journal-list {
  display: grid;
  gap: 0.55rem;
}

.slice-journal-item {
  display: grid;
  gap: 0.25rem;
  padding: 0.7rem 0.8rem;
  border-radius: 0.85rem;
  background: var(--bg-surface);
  border: 1px solid var(--border);

  strong { font-size: 0.88rem; color: var(--title); }
  p { margin: 0; font-size: 0.82rem; color: var(--text); line-height: 1.55; white-space: pre-wrap; }
}

.slice-journal-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.74rem;
  font-weight: 700;
  color: var(--muted);
}

.slice-locked-note {
  color: #b45309 !important;
  font-weight: 700;
}

.slice-ledger-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0.4rem;

  li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
    padding: 0.45rem 0.65rem;
    border-radius: 0.7rem;
    background: var(--bg-surface);
    font-size: 0.82rem;
    color: var(--title);
  }
}

.slice-empty-hint {
  margin: 0;
  font-size: 0.8rem;
  color: var(--muted);
}

.slice-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
</style>
