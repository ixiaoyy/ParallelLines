<template>
  <div class="calendar">
    <div class="calendar-heading">
      <button type="button" :aria-label="$t('上个月')" @click="moveMonth(-1)">‹</button>
      <strong aria-live="polite">{{ labelMonth }}</strong>
      <button type="button" :aria-label="$t('下个月')" @click="moveMonth(1)">›</button>
    </div>
    <div class="calendar-days">
      <span v-for="(day, index) in weekdays" :key="index" class="weekday">{{ day }}</span>
      <button
        v-for="item in days"
        :key="item.value"
        type="button"
        class="calendar__number"
        :class="{ outside: !item.inMonth, marked: pendingDates.has(item.value) }"
        :aria-label="item.value"
        :aria-pressed="item.value === date"
        @click="$emit('selectDate', item.value)"
      >
        {{ item.label }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import dayjs from 'dayjs'

const props = defineProps<{ date: string; todo: Record<string, Array<{ isChecked: boolean }>> }>()
defineEmits<{ (event: 'selectDate', date: string): void }>()

const { locale } = useI18n()
const month = ref(dayjs(props.date).startOf('month'))
watch(() => props.date, value => { month.value = dayjs(value).startOf('month') })
const labelMonth = computed(() => new Intl.DateTimeFormat(locale.value, {
  year: 'numeric', month: 'long',
}).format(month.value.toDate()))
const weekdays = computed(() => {
  const formatter = new Intl.DateTimeFormat(locale.value, { weekday: 'short' })
  const sunday = dayjs('2023-01-01')
  return Array.from({ length: 7 }, (_, i) => formatter.format(sunday.add(i, 'day').toDate()))
})

const pendingDates = computed(() => new Set(Object.keys(props.todo || {})
  .filter(day => props.todo[day].some(item => !item.isChecked))))

const days = computed(() => {
  // 计算目标年月的完整周，不用系统当前年份，也不截掉需要第六周的日期。
  const offset = month.value.day()
  const first = month.value.subtract(offset, 'day')
  const cells = Math.ceil((offset + month.value.daysInMonth()) / 7) * 7
  return Array.from({ length: cells }, (_, i) => {
    const day = first.add(i, 'day')
    return { value: day.format('YYYY-MM-DD'), label: day.date(), inMonth: day.month() === month.value.month() }
  })
})

/** 翻页只改变浏览月份；选择某一天后才交给待办组件。 */
function moveMonth(delta: -1 | 1) {
  month.value = month.value.add(delta, 'month')
}
</script>

<style scoped lang="scss">
.calendar-heading {
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) 44px;
  align-items: center;
  text-align: center;
  margin-bottom: 8px;
}
.calendar button {
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #0f172a;
  cursor: pointer;

  &:hover { background: #e8f2fc; }
  &:focus-visible { outline: 2px solid #409eff; outline-offset: -2px; }
}
.calendar-heading button {
  min-height: 44px;
  font-size: 22px;
}
.calendar-days {
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 2px;
  text-align: center;
}
.weekday {
  padding: 4px 0;
  color: #526176;
  font-size: 12px;
}
.calendar__number {
  position: relative;
  min-height: 40px;
  font-size: 14px;
  font-variant-numeric: tabular-nums;

  &.outside { color: #64748b; }
  &[aria-pressed='true'] {
    background: #409eff;
    color: #fff;
    font-weight: 600;
  }
  &.marked::after {
    content: '';
    position: absolute;
    right: 6px;
    top: 5px;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: #128756;
  }
}
</style>
