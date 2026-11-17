<script setup lang="ts">
import { currentLocale, uiText } from "@/shared/i18n/locale";
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

// 仅切换星期标题，日期键、周日起始和日历排列保持原样。
const weekdays = computed(() => currentLocale.value === "zh-CN"
  ? ["日", "一", "二", "三", "四", "五", "六"]
  : Array.from({ length: 7 }, (_, index) => new Intl.DateTimeFormat(currentLocale.value, { weekday: "short" }).format(new Date(2024, 0, 7 + index))));

const calendarCells = computed(() => {
  const [yearStr, monthStr] = props.selectedMonth.split("-");
  const year = Number(yearStr) || new Date().getFullYear();
  const month = Number(monthStr) || new Date().getMonth() + 1;
  const firstDayWeek = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();

  const journalByDate = new Map<string, SpaceJournalItem>();
  for (const j of props.journals) {
    // 只从实际填写了心情的手账选取日签，账单卡不覆盖当天真实心情。
    if (j.mood && j.entry_date.startsWith(props.selectedMonth) && !journalByDate.has(j.entry_date)) {
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

const streakDays = computed(() => {
  const activeDates = new Set<string>();
  for (const j of props.journals) activeDates.add(j.entry_date);
  for (const l of props.ledgers) activeDates.add(l.entry_date);
  if (activeDates.size === 0) return 0;

  const cursor = new Date();
  const format = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

  if (!activeDates.has(format(cursor))) {
    cursor.setDate(cursor.getDate() - 1);
  }
  let streak = 0;
  while (activeDates.has(format(cursor))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
});

const monthlyMoodBreakdown = computed(() => {
  const prefix = `${props.selectedMonth}-`;
  const counts = new Map<string, number>();
  let total = 0;
  for (const j of props.journals) {
    // 无心情的账单卡仍计入记录天数，但不参与心情分布。
    if (!j.mood || !j.entry_date.startsWith(prefix)) continue;
    counts.set(j.mood, (counts.get(j.mood) ?? 0) + 1);
    total += 1;
  }
  if (total === 0) return [];
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([moodKey, count]) => {
      const meta = getMoodMeta(moodKey);
      return {
        key: moodKey,
        emoji: meta.emoji,
        label: meta.label,
        color: meta.color,
        count,
        percent: Math.round((count * 100) / total),
      };
    });
});
</script>

<template>
  <UiCard class="space-side-card space-calendar-card">
    <header class="calendar-header">
      <button type="button" :aria-label="uiText('上个月')" @click="emit('shiftMonth', -1)">‹</button>
      <strong>🗓️ {{ selectedMonth }} {{ uiText('心情日历') }}</strong>
      <button type="button" :aria-label="uiText('下个月')" @click="emit('shiftMonth', 1)">›</button>
    </header>

    <div class="calendar-weekdays" aria-hidden="true">
      <span v-for="(day, index) in weekdays" :key="index">{{ day }}</span>
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
          <i v-if="cell.hasLedger" class="cell-ledger-dot" :title="uiText('当日有记账')"></i>
        </template>
      </button>
    </div>

    <div v-if="streakDays > 0 || monthlyMoodBreakdown.length" class="calendar-insights">
      <div v-if="streakDays > 0" class="streak-pill">
        {{ uiText('🔥 已连续记录 {count} 天', { count: streakDays }) }}
      </div>
      <div v-if="monthlyMoodBreakdown.length" class="mood-bar-wrap">
        <div class="mood-bar-track" :title="uiText('本月心情分布')">
          <i
            v-for="item in monthlyMoodBreakdown"
            :key="item.key"
            :style="{ width: `${Math.max(8, item.percent)}%`, backgroundColor: item.color }"
            :title="uiText('{emoji} {mood} {count} 篇 ({percent}%)', { emoji: item.emoji, mood: uiText(item.label), count: item.count, percent: item.percent })"
          ></i>
        </div>
        <div class="mood-bar-legend">
          <span v-for="item in monthlyMoodBreakdown.slice(0, 3)" :key="item.key">
            {{ item.emoji }} {{ item.count }}
          </span>
        </div>
      </div>
    </div>

    <div class="calendar-mood-filter">
      <span>{{ uiText('按心情筛选：') }}</span>
      <div class="mood-mini-list">
        <button
          v-for="m in JOURNAL_MOODS"
          :key="m.key"
          type="button"
          :class="{ active: filterMood === m.key }"
          :title="uiText(m.label)"
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
  border: 1px solid rgba(255, 255, 255, 0.88);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(14px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 10px 28px rgba(15, 23, 42, 0.05);
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

.calendar-insights {
  display: grid;
  gap: 0.45rem;
  padding-top: 0.25rem;
  border-top: 1px dashed var(--border);
}

.streak-pill {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text);

  b { color: #ea580c; font-weight: 900; }
}

.mood-bar-wrap {
  display: grid;
  gap: 0.3rem;
}

.mood-bar-track {
  display: flex;
  gap: 2px;
  height: 0.42rem;
  border-radius: 999px;
  overflow: hidden;
  background: var(--bg-subtle);

  i { display: block; height: 100%; border-radius: 999px; }
}

.mood-bar-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  font-size: 0.7rem;
  color: var(--muted);
  font-weight: 700;
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
