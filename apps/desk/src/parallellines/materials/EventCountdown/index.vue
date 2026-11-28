<template>
  <div
    class="event-countdown-wrapper"
    :class="`style-${currentStyle}`"
    :style="{
      color: componentSetting.textColor || '#f8fafc',
      padding: (componentSetting.padding ?? 18) + 'px',
      fontFamily: componentSetting.fontFamily || 'inherit',
      '--ec-accent': currentAccent
    }"
  >
    <!-- 顶栏：事件名 + 快捷样式/编辑入口 -->
    <div class="ec-header">
      <div class="ec-title-group">
        <span class="ec-dot" />
        <span class="ec-title" :title="eventName">{{ eventName }}</span>
      </div>
      <div class="ec-actions">
        <button
          type="button"
          class="ec-pill-btn"
          title="切换倒计时样式"
          @click.stop="cycleStyle"
        >
          {{ styleLabelMap[currentStyle] }}
        </button>
        <button
          type="button"
          class="ec-pill-btn"
          title="编辑事件与样式"
          @click.stop="openEditor"
        >
          ✎
        </button>
      </div>
    </div>

    <!-- 主体：4 种样式 -->
    <div v-if="!hasTarget" class="ec-empty" @click.stop="openEditor">
      <div class="ec-empty-title">尚未设置倒计时事件</div>
      <div class="ec-empty-sub">点击此处设置事件名称、目标时间与样式</div>
    </div>

    <!-- 样式 1：翻页卡片风 -->
    <div v-else-if="currentStyle === 'flip'" class="ec-body-flip">
      <div class="ec-status-line">{{ statusPrefix }}</div>
      <div class="flip-grid">
        <div v-for="unit in timeUnits" :key="unit.label" class="flip-cell">
          <div class="flip-card">
            <span class="flip-num">{{ unit.value }}</span>
            <span class="flip-seam" />
          </div>
          <span class="flip-label">{{ unit.label }}</span>
        </div>
      </div>
      <div class="ec-foot-line">{{ targetDateText }}</div>
    </div>

    <!-- 样式 2：极简大字风 -->
    <div v-else-if="currentStyle === 'minimal'" class="ec-body-minimal">
      <div class="ec-status-line">{{ statusPrefix }}</div>
      <div class="minimal-main">
        <span v-if="diffInfo.days > 0" class="minimal-days">
          {{ diffInfo.days }}<span class="minimal-unit">天</span>
        </span>
        <span class="minimal-hms">{{ hmsText }}</span>
      </div>
      <div class="ec-foot-line">{{ targetDateText }}</div>
    </div>

    <!-- 样式 3：进度条风 -->
    <div v-else-if="currentStyle === 'progress'" class="ec-body-progress">
      <div class="progress-top">
        <span class="progress-big">
          <template v-if="diffInfo.isReached">已到达</template>
          <template v-else-if="diffInfo.days > 0">{{ diffInfo.days }}<small>天</small> {{ pad2(diffInfo.hours) }}<small>时</small></template>
          <template v-else>{{ hmsText }}</template>
        </span>
        <span class="progress-pct">{{ progressPercent.toFixed(1) }}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-fill" :style="{ width: `${progressPercent}%` }" />
      </div>
      <div class="progress-meta">
        <span>{{ statusPrefix }}</span>
        <span>{{ targetDateText }}</span>
      </div>
    </div>

    <!-- 样式 4：环形仪表风 -->
    <div v-else class="ec-body-ring">
      <div class="ring-visual">
        <svg viewBox="0 0 100 100" class="ring-svg">
          <circle cx="50" cy="50" r="42" class="ring-track" />
          <circle
            cx="50"
            cy="50"
            r="42"
            class="ring-fill"
            :stroke-dasharray="RING_CIRCUMFERENCE"
            :stroke-dashoffset="ringDashOffset"
          />
        </svg>
        <div class="ring-center">
          <div class="ring-num">
            {{ diffInfo.days > 0 ? diffInfo.days : pad2(diffInfo.hours) }}
          </div>
          <div class="ring-unit">
            {{ diffInfo.days > 0 ? '天' : '小时' }}
          </div>
        </div>
      </div>
      <div class="ring-info">
        <div class="ec-status-line">{{ statusPrefix }}</div>
        <div class="ring-hms">{{ hmsText }}</div>
        <div class="ec-foot-line">{{ targetDateText }} · {{ progressPercent.toFixed(0) }}%</div>
      </div>
    </div>

    <!-- 快捷编辑弹窗 -->
    <easy-dialog
      v-model="editorVisible"
      title="自定义事件倒计时"
      width="min(460px, 94vw)"
      height="min(480px, 88vh)"
    >
      <el-form label-position="top" class="ec-form">
        <el-form-item label="事件名称">
          <el-input v-model="draft.eventName" maxlength="32" placeholder="例如：版本上线 / 考研 / 纪念日" />
        </el-form-item>
        <div class="ec-form-row">
          <el-form-item label="目标时间">
            <input v-model="draft.targetTime" type="datetime-local" class="ec-native-input">
          </el-form-item>
          <el-form-item label="起始时间（用于进度计算）">
            <input v-model="draft.startTime" type="datetime-local" class="ec-native-input">
          </el-form-item>
        </div>
        <el-form-item label="倒计时样式">
          <div class="style-picker">
            <button
              v-for="opt in styleOptions"
              :key="opt.value"
              type="button"
              class="style-option"
              :class="{ active: draft.style === opt.value }"
              @click="draft.style = opt.value"
            >
              <span class="style-opt-name">{{ opt.label }}</span>
              <span class="style-opt-desc">{{ opt.desc }}</span>
            </button>
          </div>
        </el-form-item>
        <el-form-item label="强调色">
          <div class="accent-row">
            <button
              v-for="color in accentPresets"
              :key="color"
              type="button"
              class="accent-dot"
              :class="{ active: draft.accentColor === color }"
              :style="{ background: color }"
              @click="draft.accentColor = color"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div style="text-align: right; padding: 10px 12px">
          <button type="button" class="btn" @click="editorVisible = false">取消</button>
          <button type="button" class="btn btn-primary" @click="saveDraft">保存</button>
        </div>
      </template>
    </easy-dialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useStore } from '@/store'

export type EventCountdownStyle = 'flip' | 'minimal' | 'progress' | 'ring'

const STYLE_OPTIONS: Array<{ value: EventCountdownStyle; label: string; desc: string }> = [
  { value: 'flip', label: '翻页卡片', desc: '四格立体数字块' },
  { value: 'minimal', label: '极简大字', desc: '通透等宽排版' },
  { value: 'progress', label: '进度条', desc: '时间流逝百分比' },
  { value: 'ring', label: '环形仪表', desc: '渐变圆环聚焦' },
]

const STYLE_LABEL_MAP: Record<EventCountdownStyle, string> = {
  flip: '翻页',
  minimal: '极简',
  progress: '进度条',
  ring: '圆环',
}

const ACCENT_PRESETS = ['#60a5fa', '#34d399', '#a78bfa', '#fb923c', '#f472b6', '#38bdf8']
const RING_CIRCUMFERENCE = 2 * Math.PI * 42

function pad2(n: number): string {
  return String(Math.max(0, Math.floor(n))).padStart(2, '0')
}

function toDatetimeLocalValue(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

function parseDateSafe(input: unknown): Date | null {
  if (typeof input !== 'string' || !input.trim()) return null
  const d = new Date(input)
  return Number.isNaN(d.getTime()) ? null : d
}

export default defineComponent({
  name: 'EventCountdown',
  props: {
    element: {
      type: Object,
      default: () => ({}),
    },
    componentSetting: {
      type: Object,
      required: true,
    },
  },
  setup(props) {
    const store = useStore()
    const now = ref(new Date())
    let timer: number | undefined

    onMounted(() => {
      timer = window.setInterval(() => {
        now.value = new Date()
      }, 1000)
    })

    onUnmounted(() => {
      if (timer) window.clearInterval(timer)
    })

    const eventName = computed(() => (props.componentSetting.eventName || '自定义事件').trim())
    const currentStyle = computed<EventCountdownStyle>(() => {
      const s = props.componentSetting.style
      return s === 'minimal' || s === 'progress' || s === 'ring' ? s : 'flip'
    })
    const currentAccent = computed(() => props.componentSetting.accentColor || '#60a5fa')

    const targetDate = computed(() => parseDateSafe(props.componentSetting.targetTime))
    const startDate = computed(() => parseDateSafe(props.componentSetting.startTime))
    const hasTarget = computed(() => targetDate.value !== null)

    const diffInfo = computed(() => {
      if (!targetDate.value) {
        return { isReached: false, days: 0, hours: 0, minutes: 0, seconds: 0 }
      }
      const deltaMs = targetDate.value.getTime() - now.value.getTime()
      const isReached = deltaMs <= 0
      const absSec = Math.floor(Math.abs(deltaMs) / 1000)
      const days = Math.floor(absSec / 86400)
      const hours = Math.floor((absSec % 86400) / 3600)
      const minutes = Math.floor((absSec % 3600) / 60)
      const seconds = absSec % 60
      return { isReached, days, hours, minutes, seconds }
    })

    const timeUnits = computed(() => [
      { label: '天', value: String(diffInfo.value.days).padStart(2, '0') },
      { label: '时', value: pad2(diffInfo.value.hours) },
      { label: '分', value: pad2(diffInfo.value.minutes) },
      { label: '秒', value: pad2(diffInfo.value.seconds) },
    ])

    const hmsText = computed(
      () => `${pad2(diffInfo.value.hours)}:${pad2(diffInfo.value.minutes)}:${pad2(diffInfo.value.seconds)}`
    )

    const statusPrefix = computed(() =>
      diffInfo.value.isReached ? '已过去' : '距离目标还有'
    )

    const targetDateText = computed(() => {
      if (!targetDate.value) return ''
      const d = targetDate.value
      return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())} ${pad2(d.getHours())}:${pad2(d.getMinutes())}`
    })

    const progressPercent = computed(() => {
      if (!targetDate.value) return 0
      const endMs = targetDate.value.getTime()
      const nowMs = now.value.getTime()
      if (nowMs >= endMs) return 100
      const fallbackStartMs = endMs - 30 * 86400 * 1000
      const startMs =
        startDate.value && startDate.value.getTime() < endMs
          ? startDate.value.getTime()
          : fallbackStartMs
      const ratio = (nowMs - startMs) / Math.max(1, endMs - startMs)
      return Math.min(100, Math.max(0, ratio * 100))
    })

    const ringDashOffset = computed(
      () => RING_CIRCUMFERENCE * (1 - progressPercent.value / 100)
    )

    const patchSetting = (patch: Record<string, any>) => {
      if (!props.element || !props.element.i) return
      const nextEl = JSON.parse(JSON.stringify(props.element))
      nextEl.componentSetting = {
        ...(nextEl.componentSetting || {}),
        ...patch,
      }
      store.editComponent(nextEl)
    }

    const cycleStyle = () => {
      const order: EventCountdownStyle[] = ['flip', 'minimal', 'progress', 'ring']
      const next = order[(order.indexOf(currentStyle.value) + 1) % order.length]
      patchSetting({ style: next })
    }

    const editorVisible = ref(false)
    const draft = reactive({
      eventName: '',
      targetTime: '',
      startTime: '',
      style: 'flip' as EventCountdownStyle,
      accentColor: '#60a5fa',
    })

    const openEditor = () => {
      const defaultTarget = new Date(Date.now() + 7 * 86400 * 1000)
      draft.eventName = props.componentSetting.eventName || '我的目标事件'
      draft.targetTime = targetDate.value
        ? toDatetimeLocalValue(targetDate.value)
        : toDatetimeLocalValue(defaultTarget)
      draft.startTime = startDate.value
        ? toDatetimeLocalValue(startDate.value)
        : toDatetimeLocalValue(new Date())
      draft.style = currentStyle.value
      draft.accentColor = currentAccent.value
      editorVisible.value = true
    }

    const saveDraft = () => {
      patchSetting({
        eventName: draft.eventName.trim() || '自定义事件',
        targetTime: draft.targetTime,
        startTime: draft.startTime,
        style: draft.style,
        accentColor: draft.accentColor,
      })
      editorVisible.value = false
    }

    return {
      pad2,
      eventName,
      currentStyle,
      currentAccent,
      hasTarget,
      diffInfo,
      timeUnits,
      hmsText,
      statusPrefix,
      targetDateText,
      progressPercent,
      ringDashOffset,
      RING_CIRCUMFERENCE,
      styleOptions: STYLE_OPTIONS,
      styleLabelMap: STYLE_LABEL_MAP,
      accentPresets: ACCENT_PRESETS,
      editorVisible,
      draft,
      cycleStyle,
      openEditor,
      saveDraft,
    }
  },
})
</script>

<style lang="scss" scoped>
.event-countdown-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
  overflow: hidden;
}

.ec-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.ec-title-group {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.ec-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--ec-accent);
  box-shadow: 0 0 10px var(--ec-accent);
  flex-shrink: 0;
}

.ec-title {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ec-actions {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}

.ec-pill-btn {
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.12);
  color: inherit;
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;

  &:hover {
    background: rgba(255, 255, 255, 0.24);
  }
}

.ec-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  border-radius: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.25);
  cursor: pointer;
  padding: 12px;
  text-align: center;

  &:hover {
    background: rgba(255, 255, 255, 0.06);
  }
}

.ec-empty-title {
  font-size: 14px;
  font-weight: 600;
}

.ec-empty-sub {
  font-size: 12px;
  opacity: 0.72;
}

.ec-status-line {
  font-size: 12px;
  opacity: 0.76;
}

.ec-foot-line {
  font-size: 11px;
  opacity: 0.68;
  font-variant-numeric: tabular-nums;
}

/* 1. 翻页卡片风 */
.ec-body-flip {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.flip-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.flip-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.flip-card {
  position: relative;
  width: 100%;
  padding: 11px 4px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.56) 0%, rgba(15, 23, 42, 0.38) 100%);
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.22),
    inset 0 -1px 0 rgba(0, 0, 0, 0.28),
    0 8px 20px rgba(2, 6, 23, 0.28);
  text-align: center;
}

.flip-num {
  font-size: clamp(18px, 2.2vw, 26px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}

.flip-seam {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: rgba(0, 0, 0, 0.28);
}

.flip-label {
  font-size: 11px;
  opacity: 0.72;
}

/* 2. 极简大字风 */
.ec-body-minimal {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.minimal-main {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  font-variant-numeric: tabular-nums;
}

.minimal-days {
  font-size: clamp(28px, 3vw, 38px);
  font-weight: 700;
  line-height: 1.1;
}

.minimal-unit {
  font-size: 14px;
  font-weight: 500;
  margin-left: 3px;
  opacity: 0.8;
}

.minimal-hms {
  font-size: clamp(18px, 2vw, 24px);
  font-weight: 600;
  color: var(--ec-accent);
}

/* 3. 进度条风 */
.ec-body-progress {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.progress-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.progress-big {
  font-size: clamp(22px, 2.5vw, 30px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;

  small {
    font-size: 13px;
    font-weight: 500;
    margin: 0 3px 0 2px;
    opacity: 0.8;
  }
}

.progress-pct {
  font-size: 13px;
  font-weight: 600;
  color: var(--ec-accent);
  font-variant-numeric: tabular-nums;
}

.progress-track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--ec-accent), #34d399);
  transition: width 0.5s ease;
}

.progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
  opacity: 0.72;
}

/* 4. 环形仪表风 */
.ec-body-ring {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ring-visual {
  position: relative;
  width: 84px;
  height: 84px;
  flex-shrink: 0;
}

.ring-svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.ring-track {
  fill: none;
  stroke: rgba(255, 255, 255, 0.14);
  stroke-width: 7;
}

.ring-fill {
  fill: none;
  stroke: var(--ec-accent);
  stroke-width: 7;
  stroke-linecap: round;
  transition: stroke-dashoffset 0.5s ease;
}

.ring-center {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.ring-num {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.ring-unit {
  font-size: 11px;
  opacity: 0.75;
}

.ring-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.ring-hms {
  font-size: 20px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* 编辑弹窗 */
.ec-form {
  padding: 6px 14px 0;
}

.ec-form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.ec-native-input {
  width: 100%;
  box-sizing: border-box;
  height: 34px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid #dcdfe6;
  font-size: 13px;
  color: #1e293b;
}

.style-picker {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}

.style-option {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  cursor: pointer;
  text-align: left;

  &.active {
    border-color: #2563eb;
    background: #eff6ff;
  }
}

.style-opt-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.style-opt-desc {
  font-size: 11px;
  color: #64748b;
}

.accent-row {
  display: flex;
  gap: 10px;
}

.accent-dot {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  border: 2px solid transparent;
  cursor: pointer;

  &.active {
    border-color: #0f172a;
    transform: scale(1.12);
  }
}
</style>
