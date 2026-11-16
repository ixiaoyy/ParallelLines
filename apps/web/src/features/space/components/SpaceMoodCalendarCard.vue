<script setup lang="ts">
import { computed } from "vue";

import {
  getMoodMeta,
  JOURNAL_MOODS,
  todayDateString,
  type SpaceJournalItem,
  type SpaceLedgerItem,
} from "@/features/space/model";
import UiCard from "@/shared/ui/Card.vue";

const props = defineProps<{
  selectedMonth: string;
  journals: SpaceJournalItem[];
  ledgers: SpaceLedgerItem[];
  filterDate: string;
  filterMood: string;
}>();

const emit = defineEmits<{
  shiftMonth: [delta: number];
  selectDate: [dateStr: string];
  selectMood: [moodKey: string];
}>();

const calendarCells = computed(() => {
  const [yearStr, monthStr] = props.selectedMonth.split("-");
  const year = Number(yearStr) || new Date().getFullYear();
  const month = Number(monthStr) || new Date().getMonth() + 1;
  const firstDayWeek = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();

  const journalByDate = new Map<string, SpaceJournalItem>();
  for (const j of props.journals) {
    if (j.entry_date.startsWith(props.selectedMonth) && !journalByDate.has(j.entry_date)) {
      journalByDate.set(j.entry_date, j);
    }
  }

  const ledgerCountByDate = new Map<string, number>();
  for (const l of props.ledgers) {
    if (l.entry_date.startsWith(props.selectedMonth)) {
      ledgerCountByDate.set(l.entry_date, (ledgerCountByDate.get(l.entry_date) ?? 0) + 1);
    }
  }

  const cells: Array<{
    key: string;
    dayNumber: number | null;
    dateStr: string;
    moodEmoji: string | null;
    moodColor: string | null;
    hasLedger: boolean;
    isToday: boolean;
  }> = [];

  for (let i = 0; i < firstDayWeek; i += 1) {
    cells.push({
      key: `pad-${i}`,
      dayNumber: null,
      dateStr: "",
      moodEmoji: null,
      moodColor: null,
      hasLedger: false,
      isToday: false,
    });
  }

  const today = todayDateString();
  for (let d = 1; d <= daysInMonth; d += 1) {
    const dateStr = `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    const journal = journalByDate.get(dateStr);
    const moodMeta = journal ? getMoodMeta(journal.mood) : null;
    cells.push({
      key: dateStr,
      dayNumber: d,
      dateStr,
      moodEmoji: moodMeta ? moodMeta.emoji : null,
      moodColor: moodMeta ? moodMeta.softBg : null,
      hasLedger: (ledgerCountByDate.get(dateStr) ?? 0) > 0,
      isToday: dateStr === today,
    });
  }
  return cells;
});
</script>

<template>
  <UiCard class="space-side-card space-calendar-card">
    <header class="calendar-header">
      <button type="button" aria-label="上个月" @click="emit('shiftMonth', -1)">‹</button>
      <strong>🗓️ {{ selectedMonth }} 心情日历</strong>
      <button type="button" aria-label="下个月" @click="emit('shiftMonth', 1)">›</button>
    </header>

    <div class="calendar-weekdays" aria-hidden="true">
      <span>日</span><span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span>
    </div>

    <div class="calendar-grid">
      <button
        v-for="cell in calendarCells"
        :key="cell.key"
        type="button"
        class="calendar-cell"
        :disabled="!cell.dayNumber"
        :class="{
          'is-empty': !cell.dayNumber,
          'is-today': cell.isToday,
          'is-selected': cell.dateStr && filterDate === cell.dateStr,
          'has-mood': Boolean(cell.moodEmoji),
        }"
        :style="cell.moodColor ? { '--cell-bg': cell.moodColor } : undefined"
        @click="cell.dateStr && emit('selectDate', cell.dateStr)"
      >
        <template v-if="cell.dayNumber">
          <em v-if="cell.moodEmoji" class="cell-mood">{{ cell.moodEmoji }}</em>
          <span class="cell-num">{{ cell.dayNumber }}</span>
          <i v-if="cell.hasLedger" class="cell-ledger-dot" title="当日有记账"></i>
        </template>
      </button>
    </div>

    <div class="calendar-mood-filter">
      <span>按心情筛选：</span>
      <div class="mood-mini-list">
        <button
          v-for="m in JOURNAL_MOODS"
          :key="m.key"
          type="button"
          :class="{ active: filterMood === m.key }"
          :title="m.label"
          @click="emit('selectMood', m.key)"
        >
          {{ m.emoji }}
        </button>
      </div>
    </div>
  </UiCard>
</template>

<style scoped lang="scss">
.space-side-card {
  display: grid;
  gap: 0.75rem;
  padding: 1rem;
  border-radius: 1.25rem;
}

.calendar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  strong { font-size: 0.88rem; font-weight: 800; color: var(--title); }

  button {
    width: 1.9rem;
    height: 1.9rem;
    border: 1px solid var(--border);
    border-radius: 50%;
    background: var(--bg-surface);
    color: var(--text);
    font-size: 1.05rem;
    line-height: 1;
    cursor: pointer;

    &:hover { color: var(--primary); border-color: var(--primary); }
  }
}

.calendar-weekdays,
.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0.28rem;
}

.calendar-weekdays span {
  text-align: center;
  font-size: 0.68rem;
  font-weight: 800;
  color: var(--muted);
}

.calendar-cell {
  position: relative;
  display: grid;
  place-items: center;
  aspect-ratio: 1;
  padding: 0;
  border: 1px solid transparent;
  border-radius: 0.6rem;
  background: var(--cell-bg, var(--bg-subtle));
  cursor: pointer;
  transition: transform 120ms ease, border-color 120ms ease;

  &:hover:not(:disabled) { transform: scale(1.08); }

  &.is-empty { background: transparent; cursor: default; }

  &.is-today { border-color: var(--primary); }

  &.is-selected {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px var(--focus-ring);
  }

  .cell-num {
    font-size: 0.7rem;
    font-weight: 800;
    color: var(--text);
  }

  .cell-mood {
    position: absolute;
    font-style: normal;
    font-size: 0.95rem;
    line-height: 1;
  }

  &.has-mood .cell-num {
    position: absolute;
    top: 1px;
    left: 3px;
    font-size: 0.52rem;
    color: var(--muted);
  }

  .cell-ledger-dot {
    position: absolute;
    right: 3px;
    bottom: 3px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #f59e0b;
  }
}

.calendar-mood-filter {
  display: grid;
  gap: 0.35rem;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--muted);
}

.mood-mini-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;

  button {
    width: 1.9rem;
    height: 1.9rem;
    border: 1px solid transparent;
    border-radius: 0.6rem;
    background: var(--bg-subtle);
    font-size: 0.95rem;
    cursor: pointer;

    &.active {
      border-color: var(--primary);
      background: var(--theme-soft-bg, rgba(64, 158, 255, 0.12));
    }
  }
}
</style>
