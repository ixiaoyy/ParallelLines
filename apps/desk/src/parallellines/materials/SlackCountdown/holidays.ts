/**
 * 摸鱼倒计时核心日历与计算逻辑（纯前端、零外部接口）。
 * 对未覆盖年份明确提示，绝不猜测法定节假日或调休。
 */

export interface HolidayRange {
  name: string
  start: string // YYYY-MM-DD
  end: string   // YYYY-MM-DD
}

export const SUPPORTED_HOLIDAY_YEARS = [2025, 2026] as const

// 中国法定节假日放假安排（按国务院办公厅正式通知维护）
export const HOLIDAY_RANGES: HolidayRange[] = [
  // 2025
  { name: '元旦', start: '2025-01-01', end: '2025-01-01' },
  { name: '春节', start: '2025-01-28', end: '2025-02-04' },
  { name: '清明节', start: '2025-04-04', end: '2025-04-06' },
  { name: '劳动节', start: '2025-05-01', end: '2025-05-05' },
  { name: '端午节', start: '2025-05-31', end: '2025-06-02' },
  { name: '国庆节/中秋节', start: '2025-10-01', end: '2025-10-08' },
  // 2026
  { name: '元旦', start: '2026-01-01', end: '2026-01-03' },
  { name: '春节', start: '2026-02-15', end: '2026-02-23' },
  { name: '清明节', start: '2026-04-04', end: '2026-04-06' },
  { name: '劳动节', start: '2026-05-01', end: '2026-05-05' },
  { name: '端午节', start: '2026-06-19', end: '2026-06-21' },
  { name: '中秋节', start: '2026-09-25', end: '2026-09-27' },
  { name: '国庆节', start: '2026-10-01', end: '2026-10-07' },
]

// 调休补班工作日（原本是周末但需要上班的日期）
export const MAKEUP_WORKDAYS = new Set<string>([
  // 2025
  '2025-01-26',
  '2025-02-08',
  '2025-04-27',
  '2025-09-28',
  '2025-10-11',
  // 2026
  '2026-01-04',
  '2026-02-14',
  '2026-02-28',
  '2026-05-09',
  '2026-09-20',
  '2026-10-10',
])

const HOLIDAY_DATE_MAP = new Map<string, string>()

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function formatYMD(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

function parseYMD(ymd: string): Date {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d)
}

for (const range of HOLIDAY_RANGES) {
  const cursor = parseYMD(range.start)
  const end = parseYMD(range.end)
  while (cursor <= end) {
    HOLIDAY_DATE_MAP.set(formatYMD(cursor), range.name)
    cursor.setDate(cursor.getDate() + 1)
  }
}

export type RestMode = 'double' | 'single' // double: 周六日双休, single: 仅周日休

export function getDayScheduleType(date: Date, restMode: RestMode): {
  isWorkday: boolean
  label: string
} {
  const ymd = formatYMD(date)
  const holidayName = HOLIDAY_DATE_MAP.get(ymd)
  if (holidayName) {
    return { isWorkday: false, label: `${holidayName}假期` }
  }
  if (MAKEUP_WORKDAYS.has(ymd)) {
    return { isWorkday: true, label: '调休工作日' }
  }
  const dow = date.getDay() // 0 = Sun, 6 = Sat
  if (dow === 0 || (restMode === 'double' && dow === 6)) {
    return { isWorkday: false, label: '周末休息' }
  }
  return { isWorkday: true, label: '工作日' }
}

function parseTimeToSeconds(hhmm: string, fallbackSeconds: number): number {
  const match = /^(\d{1,2}):(\d{2})$/.exec((hhmm || '').trim())
  if (!match) return fallbackSeconds
  const h = Math.min(23, Math.max(0, Number(match[1])))
  const m = Math.min(59, Math.max(0, Number(match[2])))
  return h * 3600 + m * 60
}

export function formatDurationHMS(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(safe / 3600)
  const m = Math.floor((safe % 3600) / 60)
  const s = safe % 60
  return `${pad2(h)}:${pad2(m)}:${pad2(s)}`
}

export interface OffWorkResult {
  status: 'rest' | 'before' | 'working' | 'done'
  badge: string
  headline: string
  subtext: string
  progress: number // 0 - 100
}

export function calcOffWorkState(
  now: Date,
  workStart: string,
  workEnd: string,
  restMode: RestMode
): OffWorkResult {
  const dayInfo = getDayScheduleType(now, restMode)
  if (!dayInfo.isWorkday) {
    return {
      status: 'rest',
      badge: dayInfo.label,
      headline: '今日休息',
      subtext: '安心放松，不看工位表',
      progress: 100,
    }
  }

  const startSec = parseTimeToSeconds(workStart, 9 * 3600)
  const rawEndSec = parseTimeToSeconds(workEnd, 18 * 3600)
  const endSec = rawEndSec > startSec ? rawEndSec : startSec + 8 * 3600
  const nowSec = now.getHours() * 3600 + now.getMinutes() * 60 + now.getSeconds()

  if (nowSec < startSec) {
    return {
      status: 'before',
      badge: dayInfo.label,
      headline: formatDurationHMS(startSec - nowSec),
      subtext: `距离上班（${workStart || '09:00'}）`,
      progress: 0,
    }
  }

  if (nowSec >= endSec) {
    return {
      status: 'done',
      badge: dayInfo.label,
      headline: '已下班',
      subtext: '今日份搬砖已完成',
      progress: 100,
    }
  }

  const progress = Math.min(100, Math.max(0, ((nowSec - startSec) / (endSec - startSec)) * 100))
  return {
    status: 'working',
    badge: dayInfo.label,
    headline: formatDurationHMS(endSec - nowSec),
    subtext: `距离下班（${workEnd || '18:00'}）· 已过 ${progress.toFixed(1)}%`,
    progress,
  }
}

export interface PaydayResult {
  daysLeft: number
  dateText: string
  isToday: boolean
  adjustedNote: string
}

function getPaydayForMonth(
  year: number,
  monthIndex: number,
  paydayDay: number,
  advanceOnRest: boolean,
  restMode: RestMode
): { date: Date; adjusted: boolean } {
  const lastDay = new Date(year, monthIndex + 1, 0).getDate()
  const clamped = Math.min(Math.max(1, Math.floor(paydayDay || 15)), lastDay)
  const target = new Date(year, monthIndex, clamped)
  if (!advanceOnRest) {
    return { date: target, adjusted: false }
  }
  let adjusted = false
  let guard = 0
  while (!getDayScheduleType(target, restMode).isWorkday && guard < 15) {
    target.setDate(target.getDate() - 1)
    adjusted = true
    guard += 1
  }
  return { date: target, adjusted }
}

export function calcPaydayCountdown(
  now: Date,
  paydayDay: number,
  advanceOnRest: boolean,
  restMode: RestMode
): PaydayResult {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  let candidate = getPaydayForMonth(
    today.getFullYear(),
    today.getMonth(),
    paydayDay,
    advanceOnRest,
    restMode
  )
  if (candidate.date < today) {
    candidate = getPaydayForMonth(
      today.getFullYear(),
      today.getMonth() + 1,
      paydayDay,
      advanceOnRest,
      restMode
    )
  }
  const diffDays = Math.round((candidate.date.getTime() - today.getTime()) / 86400000)
  return {
    daysLeft: diffDays,
    dateText: `${pad2(candidate.date.getMonth() + 1)}-${pad2(candidate.date.getDate())}`,
    isToday: diffDays === 0,
    adjustedNote: candidate.adjusted ? '遇休提前' : '',
  }
}

export interface NextHolidayResult {
  covered: boolean
  inHoliday: boolean
  name: string
  daysLeft: number
  dateText: string
  durationDays: number
  notice: string
}

export function calcNextHoliday(now: Date): NextHolidayResult {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const todayYMD = formatYMD(today)

  for (const range of HOLIDAY_RANGES) {
    if (todayYMD >= range.start && todayYMD <= range.end) {
      const start = parseYMD(range.start)
      const end = parseYMD(range.end)
      const durationDays = Math.round((end.getTime() - start.getTime()) / 86400000) + 1
      return {
        covered: true,
        inHoliday: true,
        name: range.name,
        daysLeft: 0,
        dateText: `${range.start.slice(5)} ~ ${range.end.slice(5)}`,
        durationDays,
        notice: '假期进行中',
      }
    }
    if (range.start > todayYMD) {
      const start = parseYMD(range.start)
      const end = parseYMD(range.end)
      const daysLeft = Math.round((start.getTime() - today.getTime()) / 86400000)
      const durationDays = Math.round((end.getTime() - start.getTime()) / 86400000) + 1
      return {
        covered: true,
        inHoliday: false,
        name: range.name,
        daysLeft,
        dateText: range.start.slice(5),
        durationDays,
        notice: `连休 ${durationDays} 天`,
      }
    }
  }

  const nextYear = today.getFullYear() + 1
  return {
    covered: false,
    inHoliday: false,
    name: `${nextYear} 年节假日`,
    daysLeft: -1,
    dateText: '',
    durationDays: 0,
    notice: `暂未收录 ${nextYear} 年国务院放假表`,
  }
}
