<template>
  <div
    class="todo-list-card material-todolist"
    :style="{
      '--accent': accentColor,
      fontSize: `${baseFontSize}px`,
      padding: `${cardPadding}px`
    }"
    @contextmenu="contextmenu"
  >
    <!-- 顶栏：左侧标题 + 右侧日期切换胶囊 -->
    <div class="todo-header">
      <h3 class="todo-heading">{{ headerTitle }}</h3>
      <button
        ref="dateTrigger"
        type="button"
        class="date-trigger"
        :aria-label="$t('选择待办日期')"
        aria-haspopup="dialog"
        @click.stop="openCalendar"
        @pointerdown.stop
        @mousedown.stop
        @touchstart.stop
      >
        <svg class="cal-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
          <rect x="3" y="4.5" width="18" height="16.5" rx="3" />
          <path d="M8 2.5v3.5M16 2.5v3.5M3 9.5h18" stroke-linecap="round" />
        </svg>
        <span>{{ shortDateLabel }} · {{ weekDay }}</span>
        <span class="caret" aria-hidden="true">⌄</span>
      </button>
    </div>

    <!-- 行内新增输入条 -->
    <form class="add-bar" @submit.prevent="submitNewTodo">
      <span class="add-plus" aria-hidden="true">＋</span>
      <input
        ref="newTodoInput"
        v-model="newTodoText"
        type="text"
        class="add-input"
        placeholder="添加待办"
        aria-label="添加待办"
        @keydown.stop
      >
      <button
        type="submit"
        class="add-submit"
        :disabled="!newTodoText.trim()"
      >
        添加
      </button>
    </form>

    <!-- 任务列表区域：未完成优先，已完成默认收起 -->
    <div class="todo-body">
      <ul v-if="pendingEntries.length" class="task-list">
        <li
          v-for="entry in pendingEntries"
          :key="`pending-${entry.index}-${entry.item.content}`"
          class="task-row"
          :class="{ 'is-focusing': isTaskFocusing(entry.index) }"
        >
          <button
            type="button"
            class="task-checkbox"
            role="checkbox"
            aria-checked="false"
            :aria-label="`完成 ${entry.item.content}`"
            @click.stop="handleChecked(entry.index)"
          />

          <div v-if="editingIndex !== entry.index" class="task-main" @dblclick.stop="startInlineEdit(entry.index, entry.item.content)">
            <span class="task-text">{{ entry.item.content }}</span>
            <span v-if="isTaskFocusing(entry.index)" class="focus-badge">
              <i class="focus-dot" />
              {{ focusState.running ? (focusState.mode === 'stopwatch' ? '秒表中' : '专注中') : '已暂停' }}
            </span>
          </div>
          <input
            v-else
            ref="inlineEditInput"
            v-model="editingValue"
            type="text"
            class="task-edit-input"
            @blur="commitInlineEdit(entry.index)"
            @keydown.enter.prevent="commitInlineEdit(entry.index)"
            @keydown.esc.prevent="cancelInlineEdit"
            @keydown.stop
          >

          <div class="task-actions">
            <button
              type="button"
              class="row-action-btn focus-btn"
              :title="isTaskFocusing(entry.index) ? '切换计时器' : '开始专注计时'"
              @click.stop="startFocusForTask(entry.index, entry.item.content, 'countdown')"
            >
              ⏱ 专注
            </button>
            <button
              type="button"
              class="row-action-btn stopwatch-btn"
              title="秒表正计时"
              @click.stop="startFocusForTask(entry.index, entry.item.content, 'stopwatch')"
            >
              秒表
            </button>
            <button
              type="button"
              class="row-action-btn danger"
              title="删除待办"
              aria-label="删除待办"
              @click.stop="handleRemove(entry.index)"
            >
              ×
            </button>
          </div>
        </li>
      </ul>

      <div v-else-if="!completedEntries.length" class="empty-hint">
        <span>今天还没有待办，在上方输入一条开始吧</span>
        <div class="empty-quick-timers">
          <button type="button" class="quick-timer-chip" @click="startStandaloneFocus('countdown')">
            ⏱ 25 分钟专注
          </button>
          <button type="button" class="quick-timer-chip" @click="startStandaloneFocus('stopwatch')">
            ⏲ 开启秒表
          </button>
        </div>
      </div>

      <!-- 已完成分组（默认折叠） -->
      <div v-if="completedEntries.length" class="completed-section">
        <button
          type="button"
          class="completed-toggle"
          :aria-expanded="showCompleted"
          @click="showCompleted = !showCompleted"
        >
          <span>已完成 {{ completedEntries.length }}</span>
          <span class="toggle-arrow" :class="{ open: showCompleted }">›</span>
        </button>

        <ul v-if="showCompleted" class="task-list completed-list">
          <li
            v-for="entry in completedEntries"
            :key="`done-${entry.index}-${entry.item.content}`"
            class="task-row is-done"
          >
            <button
              type="button"
              class="task-checkbox checked"
              role="checkbox"
              aria-checked="true"
              :aria-label="`取消完成 ${entry.item.content}`"
              @click.stop="handleChecked(entry.index)"
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
                <path d="M3.5 8.5l3 3 6-6.5" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </button>
            <div class="task-main">
              <span class="task-text">{{ entry.item.content }}</span>
            </div>
            <div class="task-actions">
              <button
                type="button"
                class="row-action-btn danger"
                title="删除待办"
                aria-label="删除待办"
                @click.stop="handleRemove(entry.index)"
              >
                ×
              </button>
            </div>
          </li>
        </ul>
      </div>
    </div>

    <!-- Pomatez 风格底部专注条：仅在计时开始后出现 -->
    <transition name="focus-bar-slide">
      <div v-if="focusState.active" class="focus-bar" role="region" aria-label="专注计时条">
        <div class="focus-bar-left">
          <button
            type="button"
            class="focus-mode-icon"
            :title="focusState.mode === 'countdown' ? '当前：倒计时（点击切换秒表）' : '当前：秒表（点击切换倒计时）'"
            @click="toggleFocusMode"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true">
              <circle cx="12" cy="13.5" r="7.5" />
              <path d="M12 9.5v4l2.5 1.5M9.5 3h5M12 3v3" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <span class="focus-divider" aria-hidden="true" />
          <div class="focus-task-meta">
            <span class="focus-task-title" :title="focusState.taskTitle">{{ focusState.taskTitle }}</span>
            <button
              v-if="focusState.mode === 'countdown'"
              type="button"
              class="focus-preset-chip"
              title="点击切换专注时长（15 / 25 / 45 分钟）"
              @click="cycleCountdownDuration"
            >
              {{ focusState.durationMinutes }}m 倒计时
            </button>
            <span v-else class="focus-preset-chip is-static">秒表正计时</span>
          </div>
        </div>

        <div class="focus-bar-right">
          <span class="focus-clock" :class="{ finished: focusState.finished }">{{ formattedFocusTime }}</span>
          <button
            type="button"
            class="focus-ctrl-btn primary"
            @click="togglePauseFocus"
          >
            {{ focusState.finished ? '再来一次' : focusState.running ? '暂停' : '继续' }}
          </button>
          <button
            type="button"
            class="focus-ctrl-btn"
            @click="stopFocus"
          >
            结束
          </button>
        </div>
      </div>
    </transition>

    <Teleport to="body">
      <dialog
        ref="calendarDialog"
        class="todo-calendar"
        :aria-label="$t('选择待办日期')"
        @close="closeCalendar"
      >
        <div class="calendar-toolbar">
          <strong>{{ $t('选择待办日期') }}</strong>
          <button type="button" class="calendar-close" :aria-label="$t('关闭')" @click="calendarDialog?.close()">×</button>
        </div>
        <DatePicker
          v-if="calendarOpen"
          :date="date"
          :todo="safeTodoMap"
          @select-date="updateDate"
        />
      </dialog>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { ref, reactive, computed, defineComponent, nextTick, onUnmounted, ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from '@/store'
import { ElNotification } from 'element-plus'
import DatePicker from './DatePicker.vue'
import dayjs from 'dayjs'

type FocusMode = 'countdown' | 'stopwatch'
const PRESET_DURATIONS = [15, 25, 45]

export default defineComponent({
  name: 'TodoList',
  components: {
    DatePicker
  },
  props: {
    componentSetting: {
      type: Object,
      required: true
    },
    element: {
      type: Object,
      required: true
    },
    isAction: {
      type: Boolean,
      default: false
    }
  },
  setup(props) {
    const store = useStore()
    const { locale } = useI18n()

    const accentColor = computed(() => props.componentSetting?.themeColor || '#3b82f6')
    const baseFontSize = computed(() => Number(props.componentSetting?.baseFontSize) || 14)
    const cardPadding = computed(() => Number(props.componentSetting?.padding) ?? 18)

    const date = ref(dayjs().format('YYYY-MM-DD'))
    const dateTrigger = ref<HTMLButtonElement>()
    const calendarDialog = ref<HTMLDialogElement>()
    const calendarOpen = ref(false)
    const newTodoInput = ref<HTMLInputElement>()
    const inlineEditInput = ref<HTMLInputElement | HTMLInputElement[]>()

    const newTodoText = ref('')
    const showCompleted = ref(false)
    const editingIndex = ref<number | null>(null)
    const editingValue = ref('')

    const safeTodoMap = computed<Record<string, any[]>>(() => {
      const raw = props.componentSetting?.todo
      return raw && typeof raw === 'object' ? raw : {}
    })

    const todoList: ComputedRef<any[]> = computed(
      () => Array.isArray(safeTodoMap.value[date.value]) ? safeTodoMap.value[date.value] : []
    )

    const pendingEntries = computed(() =>
      todoList.value
        .map((item, index) => ({ item, index }))
        .filter((entry) => !entry.item?.isChecked && (entry.item?.content || entry.index === editingIndex.value))
    )

    const completedEntries = computed(() =>
      todoList.value
        .map((item, index) => ({ item, index }))
        .filter((entry) => Boolean(entry.item?.isChecked) && Boolean(entry.item?.content))
    )

    const isToday = computed(() => date.value === dayjs().format('YYYY-MM-DD'))
    const headerTitle = computed(() => (isToday.value ? '今日待办' : `${dayjs(date.value).format('M月D日')}待办`))
    const shortDateLabel = computed(() => dayjs(date.value).format('M月D日'))
    const weekDay = computed(() =>
      new Intl.DateTimeFormat(locale.value || 'zh-CN', { weekday: 'short' }).format(dayjs(date.value).toDate())
    )

    // Pomatez 风格专注倒计时 / 秒表状态（仅本地会话态，不污染云配置）
    const focusState = reactive({
      active: false,
      running: false,
      finished: false,
      mode: 'countdown' as FocusMode,
      durationMinutes: 25,
      seconds: 25 * 60,
      taskDate: '',
      taskIndex: -1,
      taskTitle: '专注计时',
    })

    let focusTimer: number | null = null

    const clearFocusTimer = () => {
      if (focusTimer !== null) {
        window.clearInterval(focusTimer)
        focusTimer = null
      }
    }

    const playGentleChime = () => {
      try {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
        if (!AudioCtx) return
        const ctx = new AudioCtx()
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        osc.type = 'sine'
        osc.frequency.setValueAtTime(660, ctx.currentTime)
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.18)
        gain.gain.setValueAtTime(0.001, ctx.currentTime)
        gain.gain.exponentialRampToValueAtTime(0.14, ctx.currentTime + 0.04)
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45)
        osc.connect(gain)
        gain.connect(ctx.destination)
        osc.start()
        osc.stop(ctx.currentTime + 0.46)
      } catch {
        // 浏览器禁用自动音频时静默忽略
      }
    }

    const startTicking = () => {
      clearFocusTimer()
      focusState.running = true
      focusState.finished = false
      focusTimer = window.setInterval(() => {
        if (focusState.mode === 'stopwatch') {
          focusState.seconds += 1
          return
        }
        if (focusState.seconds > 1) {
          focusState.seconds -= 1
        } else {
          focusState.seconds = 0
          focusState.running = false
          focusState.finished = true
          clearFocusTimer()
          playGentleChime()
          ElNotification({
            title: '专注完成',
            message: `「${focusState.taskTitle}」已完成 ${focusState.durationMinutes} 分钟专注`,
            type: 'success',
            duration: 5000,
          })
        }
      }, 1000)
    }

    const startFocusForTask = (index: number, title: string, mode: FocusMode = 'countdown') => {
      focusState.active = true
      focusState.mode = mode
      focusState.taskDate = date.value
      focusState.taskIndex = index
      focusState.taskTitle = title || '专注计时'
      focusState.seconds = mode === 'countdown' ? focusState.durationMinutes * 60 : 0
      startTicking()
    }

    const startStandaloneFocus = (mode: FocusMode) => {
      focusState.active = true
      focusState.mode = mode
      focusState.taskDate = ''
      focusState.taskIndex = -1
      focusState.taskTitle = mode === 'stopwatch' ? '自由秒表' : '自由专注'
      focusState.seconds = mode === 'countdown' ? focusState.durationMinutes * 60 : 0
      startTicking()
    }

    const togglePauseFocus = () => {
      if (focusState.finished) {
        focusState.seconds = focusState.mode === 'countdown' ? focusState.durationMinutes * 60 : 0
        startTicking()
        return
      }
      if (focusState.running) {
        focusState.running = false
        clearFocusTimer()
      } else {
        startTicking()
      }
    }

    const stopFocus = () => {
      clearFocusTimer()
      focusState.active = false
      focusState.running = false
      focusState.finished = false
      focusState.taskIndex = -1
      focusState.taskDate = ''
    }

    const toggleFocusMode = () => {
      const nextMode: FocusMode = focusState.mode === 'countdown' ? 'stopwatch' : 'countdown'
      focusState.mode = nextMode
      focusState.seconds = nextMode === 'countdown' ? focusState.durationMinutes * 60 : 0
      focusState.finished = false
      if (focusState.running) {
        startTicking()
      }
    }

    const cycleCountdownDuration = () => {
      const idx = PRESET_DURATIONS.indexOf(focusState.durationMinutes)
      const nextMinutes = PRESET_DURATIONS[(idx + 1) % PRESET_DURATIONS.length]
      focusState.durationMinutes = nextMinutes
      focusState.seconds = nextMinutes * 60
      focusState.finished = false
      if (focusState.running) {
        startTicking()
      }
    }

    const isTaskFocusing = (index: number) =>
      focusState.active && focusState.taskDate === date.value && focusState.taskIndex === index

    const formattedFocusTime = computed(() => {
      const total = Math.max(0, focusState.seconds)
      const hours = Math.floor(total / 3600)
      const mins = Math.floor((total % 3600) / 60)
      const secs = total % 60
      const mm = String(mins).padStart(2, '0')
      const ss = String(secs).padStart(2, '0')
      return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`
    })

    const mutateTodoList = (mutator: (list: any[]) => void) => {
      const element = JSON.parse(JSON.stringify(props.element))
      const targetSetting = props.isAction
        ? element.actionSetting.actionClickValue.componentSetting
        : element.componentSetting
      if (!targetSetting.todo || typeof targetSetting.todo !== 'object') {
        targetSetting.todo = {}
      }
      if (!Array.isArray(targetSetting.todo[date.value])) {
        targetSetting.todo[date.value] = []
      }
      mutator(targetSetting.todo[date.value])
      if (props.isAction) {
        store.updateActionElement(element)
      }
      store.editComponent(element)
    }

    const submitNewTodo = () => {
      const content = newTodoText.value.trim()
      if (!content) return
      mutateTodoList((list) => {
        list.unshift({
          content,
          isChecked: false,
          isEditing: false,
        })
      })
      if (focusState.active && focusState.taskDate === date.value && focusState.taskIndex >= 0) {
        focusState.taskIndex += 1
      }
      newTodoText.value = ''
    }

    const handleChecked = (index: number) => {
      const wasChecked = Boolean(todoList.value[index]?.isChecked)
      mutateTodoList((list) => {
        if (list[index]) {
          list[index].isChecked = !wasChecked
          list[index].isEditing = false
        }
      })
      if (!wasChecked && isTaskFocusing(index)) {
        stopFocus()
      }
    }

    const handleRemove = (index: number) => {
      if (isTaskFocusing(index)) {
        stopFocus()
      } else if (focusState.active && focusState.taskDate === date.value && focusState.taskIndex > index) {
        focusState.taskIndex -= 1
      }
      mutateTodoList((list) => {
        list.splice(index, 1)
      })
    }

    const startInlineEdit = async (index: number, currentText: string) => {
      editingIndex.value = index
      editingValue.value = currentText
      await nextTick()
      const el = Array.isArray(inlineEditInput.value) ? inlineEditInput.value[0] : inlineEditInput.value
      el?.focus()
    }

    const commitInlineEdit = (index: number) => {
      if (editingIndex.value !== index) return
      const nextText = editingValue.value.trim()
      editingIndex.value = null
      if (!nextText) return
      mutateTodoList((list) => {
        if (list[index]) {
          list[index].content = nextText
          list[index].isEditing = false
        }
      })
      if (isTaskFocusing(index)) {
        focusState.taskTitle = nextText
      }
    }

    const cancelInlineEdit = () => {
      editingIndex.value = null
    }

    const openCalendar = () => {
      if (!calendarDialog.value || calendarDialog.value.open) return
      calendarOpen.value = true
      calendarDialog.value.showModal()
    }

    const closeCalendar = () => {
      calendarOpen.value = false
      dateTrigger.value?.focus()
    }

    const updateDate = (value: string) => {
      date.value = value
      editingIndex.value = null
      calendarDialog.value?.close()
    }

    const contextmenu = (e: MouseEvent) => {
      if (store.isLock) {
        e.stopPropagation()
      }
    }

    onUnmounted(() => {
      clearFocusTimer()
    })

    return {
      accentColor,
      baseFontSize,
      cardPadding,
      date,
      dateTrigger,
      calendarDialog,
      calendarOpen,
      newTodoInput,
      inlineEditInput,
      newTodoText,
      showCompleted,
      editingIndex,
      editingValue,
      safeTodoMap,
      pendingEntries,
      completedEntries,
      headerTitle,
      shortDateLabel,
      weekDay,
      focusState,
      formattedFocusTime,
      isTaskFocusing,
      startFocusForTask,
      startStandaloneFocus,
      togglePauseFocus,
      stopFocus,
      toggleFocusMode,
      cycleCountdownDuration,
      submitNewTodo,
      handleChecked,
      handleRemove,
      startInlineEdit,
      commitInlineEdit,
      cancelInlineEdit,
      openCalendar,
      closeCalendar,
      updateDate,
      contextmenu,
    }
  }
})
</script>

<style lang="scss" scoped>
.todo-list-card {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: #f8fafc;
  overflow: hidden;
  user-select: none;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'PingFang SC', 'Segoe UI', sans-serif;
}

.todo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-shrink: 0;
}

.todo-heading {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: #f8fafc;
}

.date-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(248, 250, 252, 0.88);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.16s ease, border-color 0.16s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.14);
    border-color: rgba(255, 255, 255, 0.28);
  }
}

.cal-icon {
  width: 14px;
  height: 14px;
  opacity: 0.78;
}

.caret {
  font-size: 12px;
  opacity: 0.65;
  transform: translateY(-1px);
}

.add-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 40px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(15, 23, 42, 0.28);
  flex-shrink: 0;
  transition: border-color 0.16s ease, background 0.16s ease;

  &:focus-within {
    border-color: rgba(96, 165, 250, 0.7);
    background: rgba(15, 23, 42, 0.42);
  }
}

.add-plus {
  font-size: 15px;
  color: rgba(248, 250, 252, 0.72);
  line-height: 1;
}

.add-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: #f8fafc;
  font-size: 14px;

  &::placeholder {
    color: rgba(203, 213, 225, 0.56);
  }
}

.add-submit {
  border: none;
  background: transparent;
  color: #60a5fa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: background 0.15s ease, opacity 0.15s ease;

  &:hover:not(:disabled) {
    background: rgba(59, 130, 246, 0.18);
  }

  &:disabled {
    opacity: 0.42;
    cursor: default;
  }
}

.todo-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-right: 2px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
}

.task-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 44px;
  padding: 6px 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  transition: background 0.15s ease;

  &:hover {
    .task-actions {
      opacity: 1;
      pointer-events: auto;
    }
  }

  &.is-done {
    opacity: 0.62;
    .task-text {
      text-decoration: line-through;
    }
  }
}

.task-checkbox {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  border: 1.6px solid rgba(226, 232, 240, 0.55);
  background: transparent;
  color: #fff;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.16s ease;

  &:hover {
    border-color: #60a5fa;
  }

  &.checked {
    background: #3b82f6;
    border-color: #3b82f6;

    svg {
      width: 12px;
      height: 12px;
    }
  }
}

.task-main {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.task-text {
  font-size: 14px;
  line-height: 1.4;
  color: #f8fafc;
  word-break: break-word;
}

.task-edit-input {
  flex: 1;
  min-width: 0;
  height: 28px;
  padding: 0 8px;
  border-radius: 6px;
  border: 1px solid rgba(96, 165, 250, 0.7);
  background: rgba(15, 23, 42, 0.55);
  color: #f8fafc;
  font-size: 14px;
  outline: none;
}

.focus-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
  font-weight: 500;
  color: #60a5fa;
  white-space: nowrap;
  flex-shrink: 0;
}

.focus-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.85);
}

.task-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  pointer-events: none;
  flex-shrink: 0;
  transition: opacity 0.15s ease;
}

.row-action-btn {
  height: 24px;
  padding: 0 7px;
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: rgba(248, 250, 252, 0.88);
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease, border-color 0.15s ease;

  &:hover {
    background: rgba(59, 130, 246, 0.28);
    border-color: rgba(96, 165, 250, 0.55);
  }

  &.danger {
    width: 24px;
    padding: 0;
    font-size: 14px;
    &:hover {
      background: rgba(239, 68, 68, 0.35);
      border-color: rgba(248, 113, 113, 0.6);
    }
  }
}

.empty-hint {
  padding: 18px 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  text-align: center;
  font-size: 13px;
  color: rgba(203, 213, 225, 0.65);
}

.empty-quick-timers {
  display: flex;
  align-items: center;
  gap: 8px;
}

.quick-timer-chip {
  height: 28px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.07);
  color: #e2e8f0;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.16s ease;

  &:hover {
    background: rgba(59, 130, 246, 0.26);
    border-color: rgba(96, 165, 250, 0.5);
  }
}

.completed-section {
  margin-top: 6px;
}

.completed-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 2px;
  border: none;
  background: transparent;
  color: rgba(203, 213, 225, 0.72);
  font-size: 13px;
  cursor: pointer;
  transition: color 0.15s ease;

  &:hover {
    color: #f8fafc;
  }
}

.toggle-arrow {
  display: inline-block;
  font-size: 14px;
  transition: transform 0.16s ease;
  &.open {
    transform: rotate(90deg);
  }
}

/* Pomatez 风格底部专注条 */
.focus-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding-top: 12px;
  margin-top: auto;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.focus-bar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex: 1;
}

.focus-mode-icon {
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  background: transparent;
  color: #3b82f6;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  border-radius: 8px;
  transition: background 0.15s ease;

  svg {
    width: 21px;
    height: 21px;
  }

  &:hover {
    background: rgba(59, 130, 246, 0.18);
  }
}

.focus-divider {
  width: 1px;
  height: 18px;
  background: rgba(255, 255, 255, 0.16);
  flex-shrink: 0;
}

.focus-task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.focus-task-title {
  font-size: 13px;
  font-weight: 500;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.focus-preset-chip {
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: rgba(203, 213, 225, 0.78);
  font-size: 11px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;

  &:hover:not(.is-static) {
    background: rgba(255, 255, 255, 0.14);
    color: #fff;
  }

  &.is-static {
    cursor: default;
  }
}

.focus-bar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.focus-clock {
  font-size: 21px;
  font-weight: 700;
  color: #f8fafc;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  margin-right: 4px;

  &.finished {
    color: #34d399;
  }
}

.focus-ctrl-btn {
  height: 30px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  background: rgba(255, 255, 255, 0.06);
  color: #f8fafc;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s ease, border-color 0.15s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.14);
  }

  &.primary {
    background: #3b82f6;
    border-color: #3b82f6;
    color: #fff;

    &:hover {
      background: #2563eb;
      border-color: #2563eb;
    }
  }
}

.focus-bar-slide-enter-active,
.focus-bar-slide-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.focus-bar-slide-enter-from,
.focus-bar-slide-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@media (hover: none), (max-width: 640px) {
  .task-actions {
    opacity: 1;
    pointer-events: auto;
  }

  .focus-bar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .focus-bar-right {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>

<style lang="scss">
.todo-calendar {
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 16px;
  padding: 14px;
  background: rgba(15, 23, 42, 0.94);
  color: #f8fafc;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45);
  max-width: calc(100vw - 24px);

  &::backdrop {
    background: rgba(15, 23, 42, 0.55);
    backdrop-filter: blur(6px);
  }

  .calendar-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
    font-size: 14px;
  }

  .calendar-close {
    width: 28px;
    height: 28px;
    border-radius: 999px;
    border: none;
    background: rgba(255, 255, 255, 0.1);
    color: #f8fafc;
    font-size: 16px;
    cursor: pointer;
    &:hover {
      background: rgba(255, 255, 255, 0.2);
    }
  }
}
</style>
