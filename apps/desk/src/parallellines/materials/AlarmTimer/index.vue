<template>
  <section ref="card" class="alarm-card" aria-label="闹钟与定时" :style="appearance">
    <div>
      <div aria-live="assertive" aria-atomic="true">
        <div v-if="alerts.length" class="alarm-alert">
          <div>
            <strong>到点提醒</strong>
            <ul>
              <li v-for="(alert, index) in alerts" :key="index">{{ alert }}</li>
            </ul>
          </div>
          <button class="alarm-button" type="button" @click="dismissAlerts">知道了</button>
        </div>
      </div>

      <header class="alarm-heading">
        <h2>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="13" r="7.5" />
            <path d="M12 9v4l2.5 1.5M5.5 3 3 5.5M18.5 3 21 5.5M6.5 19l-1 2M17.5 19l1 2" />
          </svg>
          闹钟与定时
        </h2>
        <div class="alarm-tabs" role="tablist" aria-label="提醒类型">
          <button
            v-for="item in tabs"
            :id="cardId + '-tab-' + item.value"
            :key="item.value"
            type="button"
            class="alarm-tab"
            role="tab"
            :aria-selected="tab === item.value"
            :aria-controls="cardId + '-' + item.value"
            :tabindex="tab === item.value ? 0 : -1"
            @click="selectTab(item.value)"
            @keydown="handleTabKey"
          >{{ item.label }}</button>
        </div>
      </header>
    </div>

    <div
      v-show="tab === 'alarms'"
      :id="cardId + '-alarms'"
      class="alarm-panel"
      role="tabpanel"
      :aria-labelledby="cardId + '-tab-alarms'"
    >
      <div class="alarm-tools">
        <p v-if="timer.mode === 'running'" class="alarm-chip">计时中 {{ formattedRemaining }}</p>
        <p v-else class="alarm-hint">按设备时间每日重复。</p>
        <button ref="addButton" class="alarm-button alarm-primary" type="button" @click="openAlarmForm()">
          添加闹钟
        </button>
      </div>
      <form
        v-if="draft"
        class="alarm-form"
        novalidate
        @submit.prevent="saveAlarm"
        @pointerdown.stop
        @mousedown.stop
        @touchstart.stop
        @keydown.stop
      >
        <div class="alarm-fields">
          <label>
            时间
            <input ref="timeInput" v-model="draft.time" type="time" step="60" required>
          </label>
          <label>
            备注（选填）
            <input v-model="draft.label" type="text" placeholder="例如：点午饭">
          </label>
        </div>
        <p v-if="alarmError" class="alarm-error" role="alert">{{ alarmError }}</p>
        <div class="alarm-actions">
          <button class="alarm-button alarm-primary" type="submit">保存</button>
          <button class="alarm-button" type="button" @click="closeAlarmForm">取消</button>
        </div>
      </form>

      <p v-if="alarms.length === 0 && !draft" class="alarm-empty">还没有日常闹钟。</p>
      <ul v-else-if="alarms.length" class="alarm-list">
        <li v-for="alarm in alarms" :key="alarm.id" class="alarm-row">
          <div class="alarm-description">
            <time :datetime="alarm.time">{{ alarm.time }}</time>
            <span>{{ alarm.label || '日常提醒' }}</span>
          </div>
          <div class="alarm-actions">
            <button
              type="button"
              role="switch"
              class="alarm-button"
              :class="{ 'alarm-on': alarm.enabled }"
              :aria-label="alarm.time + ' ' + (alarm.label || '日常提醒')"
              :aria-checked="alarm.enabled"
              @click="toggleAlarm(alarm)"
            >{{ alarm.enabled ? '已开启' : '已关闭' }}</button>
            <button class="alarm-button" type="button" @click="openAlarmForm(alarm)">编辑</button>
            <button class="alarm-button alarm-delete" type="button" @click="deleteAlarm(alarm.id)">删除</button>
          </div>
        </li>
      </ul>
    </div>

    <div
      v-show="tab === 'timer'"
      :id="cardId + '-timer'"
      class="alarm-panel"
      role="tabpanel"
      :aria-labelledby="cardId + '-tab-timer'"
    >
      <div class="alarm-readout">
        <span class="alarm-digits" role="timer" aria-live="off">{{ formattedRemaining }}</span>
        <span class="alarm-chip" role="status">{{ timerStatus }}</span>
      </div>
      <div class="alarm-presets" aria-label="快捷开始">
        <button
          v-for="minutes in presets"
          :key="minutes"
          class="alarm-button"
          type="button"
          @click="startTimer(minutes)"
        >{{ minutes }} 分钟</button>
      </div>
      <form
        class="alarm-timer-form"
        novalidate
        @submit.prevent="handleTimerAction"
        @keydown.stop
      >
        <label>
          自定义分钟
          <input
            v-model="minutesInput"
            type="number"
            inputmode="numeric"
            :min="1"
            :max="MAX_MINUTES"
            step="1"
            :disabled="timer.mode === 'running' || timer.mode === 'paused'"
            @pointerdown.stop
            @mousedown.stop
            @touchstart.stop
          >
        </label>
        <div class="alarm-actions">
          <button class="alarm-button alarm-primary" type="submit">{{ timerAction }}</button>
          <button class="alarm-button" type="button" @click="resetTimer">重置</button>
        </div>
      </form>
      <p v-if="timerError" class="alarm-error" role="alert">{{ timerError }}</p>
    </div>

    <footer class="alarm-footer">
      <div class="alarm-actions">
        <button
          v-if="!audioReady && audioAvailable"
          class="alarm-button"
          type="button"
          @click="unlockAudio"
        >开启提示音</button>
        <button
          class="alarm-button"
          type="button"
          :disabled="notificationPending || (!notificationEnabled && (permission === 'denied' || permission === 'unavailable'))"
          @click="toggleSystemNotifications"
        >{{ notificationEnabled ? '关闭系统通知' : '开启系统通知' }}</button>
      </div>
      <p class="alarm-hint">{{ notificationHint }}</p>
      <p v-if="audioHint" class="alarm-hint">{{ audioHint }}</p>
      <p class="alarm-hint">提醒需保持工作台页面打开。</p>
    </footer>
  </section>
</template>

<script lang="ts">
// 同一页面内共用一个音频上下文；切换宽窄屏或组件标签不撤销用户的音频手势。
let reminderAudio: AudioContext | undefined
</script>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, type PropType } from 'vue'
import { useStore } from '@/store'
import { uid } from '@/utils'

type Alarm = { id: string; time: string; label: string; enabled: boolean }
type Tab = 'alarms' | 'timer'
type TimerState = {
  mode: 'idle' | 'running' | 'paused' | 'finished'
  durationMs: number
  remainingMs: number
  deadline: number | null
}
type CardSession = {
  tab: Tab
  timer: TimerState
  fired: Record<string, number>
  alerts: string[]
}
type SystemPermission = NotificationPermission | 'unavailable'

const MINUTE = 60_000
const MAX_MINUTES = 1440
const DEFAULT_MINUTES = 25
const MAX_ALARM_DELAY = 2 * MINUTE
const timePattern = /^(?:[01]\d|2[0-3]):[0-5]\d$/
const presets = [5, 15, 25, 45]
const tabs: { value: Tab; label: string }[] = [
  { value: 'alarms', label: '日常闹钟' },
  { value: 'timer', label: '快捷倒计时' }
]

defineOptions({ name: 'AlarmTimer' })

const props = defineProps({
  element: Object as PropType<ComponentOptions>,
  componentSetting: {
    type: Object as PropType<Record<string, unknown>>,
    default: () => ({})
  },
  isAction: Boolean
})
const store = useStore()
const setting = computed(() => props.componentSetting ?? {})
const cardId = 'pl-alarm-' + (props.element?.i || uid()) + (props.isAction ? '-action' : '')
const sessionKey = 'pl-desk:alarm:v1:' + cardId
const card = ref<HTMLElement>()
const timeInput = ref<HTMLInputElement>()
const addButton = ref<HTMLButtonElement>()

/** 为默认显示、重置或存储恢复生成完整的空闲倒计时状态。 */
function idleTimer(durationMs = DEFAULT_MINUTES * MINUTE): TimerState {
  return { mode: 'idle', durationMs, remainingMs: durationMs, deadline: null }
}

/** 从当前浏览器标签页恢复计时、已触发时刻和横幅，避免随组件重挂载而丢失。 */
function restoreSession(): CardSession {
  const fallback: CardSession = { tab: 'alarms', timer: idleTimer(), fired: {}, alerts: [] }
  try {
    const saved = JSON.parse(sessionStorage.getItem(sessionKey) || 'null') as Partial<CardSession> | null
    if (!saved) return fallback

    const timer = saved.timer
    if (
      timer && ['idle', 'paused', 'running', 'finished'].includes(timer.mode) &&
      Number.isInteger(timer.durationMs / MINUTE) &&
      timer.durationMs >= MINUTE && timer.durationMs <= MAX_MINUTES * MINUTE &&
      Number.isFinite(timer.remainingMs) && timer.remainingMs >= 0 && timer.remainingMs <= timer.durationMs &&
      (timer.mode === 'running' ? Number.isFinite(timer.deadline) : timer.deadline === null)
    ) {
      fallback.timer = timer
    }
    if (saved.tab === 'timer') fallback.tab = 'timer'
    if (saved.fired && typeof saved.fired === 'object' && !Array.isArray(saved.fired)) {
      fallback.fired = Object.fromEntries(Object.entries(saved.fired).filter(([, day]) => Number.isInteger(day)))
    }
    if (Array.isArray(saved.alerts)) {
      fallback.alerts = saved.alerts.filter((entry): entry is string => typeof entry === 'string')
    }
  } catch {
    // 标签页存储不可用或损坏时，本次挂载仍可计时、提醒。
  }
  return fallback
}

const session = shallowRef(restoreSession())
const tab = computed(() => session.value.tab)
const timer = computed(() => session.value.timer)
const alerts = computed(() => session.value.alerts)
const minutesInput = ref<number | string>(timer.value.durationMs / MINUTE)
const now = ref(Date.now())
const draft = ref<Pick<Alarm, 'id' | 'time' | 'label'> | null>(null)
const alarmError = ref('')
const timerError = ref('')
const appearance = computed(() => ({
  color: typeof setting.value.textColor === 'string' && setting.value.textColor
    ? setting.value.textColor
    : '#f8fafc',
  fontFamily: typeof setting.value.fontFamily === 'string' && setting.value.fontFamily
    ? setting.value.fontFamily
    : 'inherit'
}))

const alarms = computed<Alarm[]>(() => {
  // 导入的配置先逐条校验；无效时间、非对象或冲突 ID 不参与界面和提醒。
  if (!Array.isArray(setting.value.alarms)) return []
  const ids = new Set<string>()
  return setting.value.alarms.flatMap((entry: unknown) => {
    if (!entry || typeof entry !== 'object') return []
    const { id, time, label, enabled } = entry as Partial<Alarm>
    if (typeof id !== 'string' || !id || ids.has(id) || typeof time !== 'string' || !timePattern.test(time)) return []
    ids.add(id)
    return [{ id, time, label: typeof label === 'string' ? label : '', enabled: enabled === true }]
  })
})

const remainingMs = computed(() => {
  const state = timer.value
  return state.deadline === null ? state.remainingMs : Math.max(0, state.deadline - now.value)
})
const formattedRemaining = computed(() => {
  const seconds = Math.ceil(remainingMs.value / 1000)
  const clock = [Math.floor(seconds / 60) % 60, seconds % 60]
  if (seconds >= 3600) clock.unshift(Math.floor(seconds / 3600))
  return clock.map(unit => String(unit).padStart(2, '0')).join(':')
})
const timerAction = computed(() => (
  timer.value.mode === 'running' ? '暂停' : timer.value.mode === 'paused' ? '继续' : '开始'
))
const timerStatus = computed(() => ({
  idle: '待开始', running: '计时中', paused: '已暂停', finished: '已到点'
}[timer.value.mode]))

/** 仅在运行状态有变化时写入标签页存储，避免按秒写入。 */
function updateSession(patch: Partial<CardSession>) {
  session.value = { ...session.value, ...patch }
  try {
    sessionStorage.setItem(sessionKey, JSON.stringify(session.value))
  } catch {
    // 存储限制不影响这次挂载的倒计时和卡片提示。
  }
}

/** 经工作台已有的保存入口更新当前物料设置，保留其布局及其他配置。 */
function saveSetting(patch: Record<string, unknown>) {
  const element = props.element
  if (!element?.i) return
  const componentSetting = { ...setting.value, ...patch }
  if (props.isAction) {
    // 弹出的物料配置位于触发物料的交互设置中，不能覆盖触发卡片自己的设置。
    const action = element.actionSetting
    if (action?.actionClickValue.material !== 'AlarmTimer' || store.actionElement?.i !== element.i) return
    const next = {
      ...element,
      actionSetting: { ...action, actionClickValue: { ...action.actionClickValue, componentSetting } }
    }
    store.editComponent(next)
    store.updateActionElement(next)
  } else {
    store.editComponent({ ...element, componentSetting })
  }
}

/** 点击或键盘选中标签，并保存在本次浏览器会话。 */
function selectTab(next: Tab) {
  if (tab.value !== next) updateSession({ tab: next })
}

/** 遵循标签组的方向键/Home/End 键盘导航，焦点不跳出卡片。 */
function handleTabKey(event: KeyboardEvent) {
  let next: Tab
  if (event.key === 'Home') next = 'alarms'
  else if (event.key === 'End') next = 'timer'
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') next = tab.value === 'alarms' ? 'timer' : 'alarms'
  else return

  event.preventDefault()
  event.stopPropagation()
  selectTab(next)
  document.getElementById(cardId + '-tab-' + next)?.focus()
}

/** 打开表单，以已有时间或设备当前时间的下一分钟作为初值。 */
function openAlarmForm(alarm?: Alarm) {
  const nextMinute = new Date(Date.now() + MINUTE)
  const time = [nextMinute.getHours(), nextMinute.getMinutes()].map(part => String(part).padStart(2, '0')).join(':')
  draft.value = { id: alarm?.id || '', time: alarm?.time || time, label: alarm?.label || '' }
  alarmError.value = ''
  void nextTick(() => timeInput.value?.focus())
}

/** 退出编辑并把键盘焦点返回添加入口。 */
function closeAlarmForm() {
  draft.value = null
  alarmError.value = ''
  void nextTick(() => addButton.value?.focus())
}

/** 保存经 24 小时制校验的闹钟，编辑不改变已开关状态。 */
function saveAlarm() {
  const entry = draft.value
  if (!entry) return
  if (!timePattern.test(entry.time)) {
    alarmError.value = '请输入有效的时间（HH:mm）。'
    return
  }

  const previous = alarms.value.find(alarm => alarm.id === entry.id)
  const updated = { id: previous?.id || uid(), time: entry.time, label: entry.label.trim(), enabled: previous?.enabled ?? true }
  saveSetting({ alarms: previous
    ? alarms.value.map(alarm => alarm.id === previous.id ? updated : alarm)
    : [...alarms.value, updated] })
  if (updated.enabled) void unlockAudio()
  closeAlarmForm()
}

/** 切换指定闹钟；已提醒的时刻仍保留，避免反复切开关重复提醒。 */
function toggleAlarm(alarm: Alarm) {
  saveSetting({ alarms: alarms.value.map(entry => entry.id === alarm.id ? { ...entry, enabled: !entry.enabled } : entry) })
  if (!alarm.enabled) void unlockAudio()
}

/** 删除指定闹钟以及仅属于它的会话提醒记录。 */
function deleteAlarm(id: string) {
  saveSetting({ alarms: alarms.value.filter(alarm => alarm.id !== id) })
  const fired = { ...session.value.fired }
  if (Object.prototype.hasOwnProperty.call(fired, id)) {
    delete fired[id]
    updateSession({ fired })
  }
  if (draft.value?.id === id) closeAlarmForm()
}

/** 判断系统通知可用性，不在读取状态时发起权限请求。 */
function readPermission(): SystemPermission {
  return window.isSecureContext && typeof window.Notification === 'function'
    ? window.Notification.permission
    : 'unavailable'
}

const permission = ref<SystemPermission>(readPermission())
const notificationPending = ref(false)
const notificationEnabled = computed(() => setting.value.systemNotifications === true && permission.value === 'granted')
const notificationHint = computed(() => {
  if (permission.value === 'unavailable') return '此环境不支持系统通知。'
  if (permission.value === 'denied') return '浏览器已阻止通知，可在站点设置中修改。'
  if (notificationEnabled.value) return '系统通知已开启。'
  return ''
})
let notificationFailed = false
let mounted = false

/** 仅通知按钮直接调用：已有权限时只保存本卡开关，不重复弹窗。 */
async function toggleSystemNotifications() {
  if (notificationPending.value) return
  if (notificationEnabled.value) {
    saveSetting({ systemNotifications: false })
    return
  }

  permission.value = notificationFailed ? 'unavailable' : readPermission()
  if (permission.value === 'default') {
    notificationPending.value = true
    try {
      permission.value = await window.Notification.requestPermission()
    } catch {
      notificationFailed = true
      permission.value = 'unavailable'
    } finally {
      notificationPending.value = false
    }
  }
  if (mounted && permission.value === 'granted') saveSetting({ systemNotifications: true })
}

const audioAvailable = typeof window.AudioContext === 'function'
const audioReady = ref(reminderAudio?.state === 'running')
const audioHint = ref(audioAvailable ? '' : '此浏览器不支持提示音。')

/** 用户在卡片内开启声音或启动提醒时解锁浏览器的音频上下文。 */
async function unlockAudio() {
  if (!audioAvailable) return
  try {
    reminderAudio ??= new window.AudioContext()
    if (reminderAudio.state !== 'running') await reminderAudio.resume()
    audioReady.value = reminderAudio.state === 'running'
    audioHint.value = audioReady.value ? '' : '提示音还未开启，请重试。'
  } catch {
    audioReady.value = false
    audioHint.value = '无法播放提示音，卡内提醒仍可用。'
  }
}

/** 合成两个带短淡入淡出的柔和音符；浏览器未解锁时保留视觉提醒。 */
function playChime() {
  const audio = reminderAudio
  if (audio?.state !== 'running') {
    audioReady.value = false
    if (audioAvailable) audioHint.value = '浏览器尚未允许播放，点击「开启提示音」试试。'
    return
  }

  try {
    const begin = audio.currentTime
    ;[440, 587.33].forEach((frequency, index) => {
      const start = begin + 0.2 * index
      const tone = audio.createOscillator()
      const envelope = audio.createGain()
      tone.type = 'sine'
      tone.frequency.value = frequency
      envelope.gain.setValueAtTime(0.001, start)
      envelope.gain.exponentialRampToValueAtTime(0.075, start + 0.035)
      envelope.gain.exponentialRampToValueAtTime(0.001, start + 0.32)
      tone.connect(envelope)
      envelope.connect(audio.destination)
      tone.onended = () => {
        tone.disconnect()
        envelope.disconnect()
      }
      tone.start(start)
      tone.stop(start + 0.325)
    })
  } catch {
    audioReady.value = false
    audioHint.value = '提示音播放失败，卡内提醒仍可用。'
  }
}

/** 关闭横幅不影响闹钟和倒计时状态。 */
function dismissAlerts() {
  updateSession({ alerts: [] })
}

/** 用有效分钟开始新计时；每张卡同时只运行一个截止时间。 */
function startTimer(minutes: number) {
  if (!Number.isInteger(minutes) || minutes < 1 || minutes > MAX_MINUTES) {
    timerError.value = `请输入 1–${MAX_MINUTES} 之间的整数分钟。`
    return
  }

  const durationMs = minutes * MINUTE
  const startedAt = Date.now()
  now.value = startedAt
  minutesInput.value = minutes
  timerError.value = ''
  updateSession({ timer: { mode: 'running', durationMs, remainingMs: durationMs, deadline: startedAt + durationMs } })
  void unlockAudio()
}

/** 主按钮根据当前状态开始、暂停或恢复；恢复时只计暂停前剩下的时间。 */
function handleTimerAction() {
  const wasRunning = timer.value.mode === 'running'
  tick()
  const state = timer.value
  if (wasRunning && state.mode === 'finished') return
  if (state.mode === 'running' && state.deadline !== null) {
    updateSession({ timer: { ...state, mode: 'paused', deadline: null, remainingMs: state.deadline - now.value } })
  } else if (state.mode === 'paused') {
    updateSession({ timer: { ...state, mode: 'running', deadline: now.value + state.remainingMs } })
    void unlockAudio()
  } else {
    startTimer(Number(minutesInput.value))
  }
}

/** 取消现有计时，恢复最近设定的时长，不触发提醒。 */
function resetTimer() {
  timerError.value = ''
  minutesInput.value = timer.value.durationMs / MINUTE
  updateSession({ timer: idleTimer(timer.value.durationMs) })
}

// 首次打开时只检查当前这一分钟；之后只检查两次扫描跨过的到点区间。
let lastChecked = Math.floor(now.value / MINUTE) * MINUTE - 1
let ticker: number | undefined

/** 返回设备时区的日期数字，用于去重标记和跨日判断。 */
function localDay(date: Date) {
  return date.getFullYear() * 10_000 + (date.getMonth() + 1) * 100 + date.getDate()
}

/** 用真实时间扫描新到点的提醒，支持页面短暂节流并且同条闹钟当天同一设定时刻只提醒一次。 */
function tick() {
  const current = Date.now()
  now.value = current
  const previous = lastChecked
  lastChecked = current
  const state = timer.value
  const messages: string[] = []
  const patch: Partial<CardSession> = {}

  if (state.deadline !== null && current >= state.deadline) {
    patch.timer = { ...state, mode: 'finished', deadline: null, remainingMs: 0 }
    messages.push(`${state.durationMs / MINUTE} 分钟倒计时结束`)
  }

  if (Math.floor(current / MINUTE) > Math.floor(previous / MINUTE)) {
    const earliest = Math.max(previous, current - MAX_ALARM_DELAY)
    const today = new Date(current)
    const firstDay = new Date(earliest)
    const days = localDay(firstDay) === localDay(today) ? [today] : [firstDay, today]
    const fired: Record<string, number> = Object.assign(Object.create(null), session.value.fired)
    for (const day of days) {
      for (const alarm of alarms.value) {
        if (!alarm.enabled) continue
        const [hour, minute] = alarm.time.split(':').map(Number)
        // 只对同一天同一设定时间去重；编辑到当天更晚的时间可以再次提醒。
        const stamp = localDay(day) * 10_000 + hour * 100 + minute
        if (fired[alarm.id] === stamp) continue
        const due = new Date(day)
        const dueTime = due.setHours(hour, minute, 0, 0)
        // 夏令时跳过的本地时刻不存在，不把它挪到别的时刻提醒。
        if (due.getHours() !== hour || due.getMinutes() !== minute || dueTime <= earliest || dueTime > current) continue
        fired[alarm.id] = stamp
        patch.fired = fired
        messages.push(`${alarm.time} · ${alarm.label || '日常提醒'}`)
      }
    }
  }

  if (!messages.length) return
  updateSession({ ...patch, alerts: messages })
  // 桌面矮卡从编辑区回到顶部，确保到点横幅进入卡内视口。
  void nextTick(() => { if (card.value) card.value.scrollTop = 0 })
  playChime()
  if (setting.value.systemNotifications === true && !notificationFailed && readPermission() === 'granted') {
    try {
      new window.Notification('闹钟与定时', { body: messages.join('\n'), silent: true })
    } catch {
      // 某些浏览器允许授权却不支持由页面发出通知；下次不再尝试，保留卡内横幅。
      notificationFailed = true
      permission.value = 'unavailable'
    }
  }
}

/** 页面重新可见或获得焦点时立即校准倒计时和浏览器权限。 */
function refreshPageState() {
  permission.value = notificationFailed ? 'unavailable' : readPermission()
  audioReady.value = reminderAudio?.state === 'running'
  if (audioReady.value) audioHint.value = ''
  tick()
}

onMounted(() => {
  mounted = true
  refreshPageState()
  ticker = window.setInterval(tick, 1000)
  window.addEventListener('focus', refreshPageState)
  document.addEventListener('visibilitychange', refreshPageState)
})

onUnmounted(() => {
  mounted = false
  if (ticker !== undefined) window.clearInterval(ticker)
  window.removeEventListener('focus', refreshPageState)
  document.removeEventListener('visibilitychange', refreshPageState)
})
</script>

<style scoped>
.alarm-card {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  min-width: 0;
  padding: clamp(6px, 1.4vh, 12px) 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 15px;
  background-color: rgba(15, 23, 42, 0.62);
  backdrop-filter: blur(16px);
  color-scheme: dark;
  font-size: 14px;
  line-height: 1.45;
  overflow: auto;
  scrollbar-width: thin;
  overflow-wrap: anywhere;
  display: grid;
  align-content: start;
  gap: 10px;
}


.alarm-heading,
.alarm-tools,
.alarm-actions,
.alarm-tabs,
.alarm-presets,
.alarm-fields,
.alarm-readout,
.alarm-timer-form,
.alarm-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.alarm-heading,
.alarm-tools,
.alarm-row {
  justify-content: space-between;
}

.alarm-heading h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font: inherit;
  font-weight: 650;
}

.alarm-heading svg {
  flex: 0 0 19px;
  width: 19px;
  height: 19px;
  color: #93c5fd;
}

.alarm-tabs {
  padding: 2px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.045);
}

.alarm-button,
.alarm-tab,
.alarm-fields input,
.alarm-timer-form input {
  box-sizing: border-box;
  max-width: 100%;
  min-height: 34px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 8px;
  color: inherit;
  font: inherit;
  line-height: 1.4;
}

.alarm-button,
.alarm-tab {
  padding: 5px 9px;
  background: rgba(255, 255, 255, 0.08);
  cursor: pointer;
}

.alarm-card :is(button, input):focus-visible {
  outline: 2px solid #bfdbfe;
  outline-offset: 1px;
}

.alarm-card button:hover:not(:disabled) {
  background-color: rgba(147, 197, 253, 0.22);
}

.alarm-card button:disabled {
  cursor: default;
  opacity: 0.55;
}

.alarm-tab {
  min-height: 29px;
  border-color: transparent;
  padding-block: 3px;
  background: transparent;
}

.alarm-tab[aria-selected="true"] {
  border-color: rgba(147, 197, 253, 0.32);
  background: rgba(147, 197, 253, 0.14);
  color: #dbeafe;
  font-weight: 650;
}

.alarm-primary {
  border-color: rgba(147, 197, 253, 0.52);
  background: rgba(59, 130, 246, 0.22);
}

.alarm-on {
  border-color: rgba(167, 243, 208, 0.39);
  background: rgba(52, 211, 153, 0.15);
  color: #d1fae5;
}

.alarm-delete {
  color: #ffe4e6;
}

.alarm-panel,
.alarm-footer,
.alarm-list,
.alarm-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
}

.alarm-form,
.alarm-row {
  padding: 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.065);
}

.alarm-description {
  min-width: 0;
}

.alarm-description time {
  margin-inline-end: 8px;
  font-weight: 700;
}

.alarm-fields label {
  flex: 1 1 7.5rem;
  min-width: 0;
}

.alarm-fields label:last-child {
  flex-basis: 11rem;
}

.alarm-fields input,
.alarm-timer-form input {
  padding: 4px 8px;
  background: rgba(15, 23, 42, 0.66);
  -webkit-user-select: text;
  user-select: text;
}

.alarm-fields input {
  display: block;
  width: 100%;
  margin-top: 3px;
}

.alarm-timer-form input {
  width: 5rem;
  margin-inline: 3px 0;
}

.alarm-fields input::placeholder {
  color: #c1cbda;
}

.alarm-readout {
  gap: 10px;
}

.alarm-digits {
  font-size: clamp(26px, 5vw, 38px);
  line-height: 1.1;
  font-weight: 700;
}

.alarm-digits,
.alarm-chip,
.alarm-description time {
  font-variant-numeric: tabular-nums;
}

.alarm-chip {
  padding: 2px 8px;
  border: 1px solid rgba(147, 197, 253, 0.25);
  border-radius: 999px;
  background: rgba(147, 197, 253, 0.13);
  color: #dbeafe;
  font-size: 12px;
}

.alarm-alert {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(253, 230, 138, 0.5);
  border-radius: 10px;
  background: rgba(217, 119, 6, 0.25);
  color: #fef3c7;
}

.alarm-alert > div {
  flex: 1 1 8rem;
  min-width: 0;
}

.alarm-footer {
  padding-top: 8px;
  border-top: 1px solid rgba(255, 255, 255, 0.14);
  gap: 4px;
}

.alarm-hint,
.alarm-empty,
.alarm-error {
  color: #d2dbe7;
  font-size: 12px;
}

.alarm-hint:empty {
  display: none;
}

.alarm-error {
  color: #fecdd3;
}

@media (max-width: 959px) {
  .alarm-button,
  .alarm-tab,
  .alarm-fields input,
  .alarm-timer-form input {
    min-height: 44px;
  }
}
</style>
