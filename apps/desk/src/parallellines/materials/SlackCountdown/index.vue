<template>
  <div
    class="slack-countdown-wrapper"
    :style="{
      color: componentSetting.textColor || '#f8fafc',
      '--slack-padding': (componentSetting.padding ?? 18) + 'px',
      fontFamily: componentSetting.fontFamily || 'inherit'
    }"
  >
    <div class="slack-main">
      <div class="slack-header">
        <span class="slack-title">下班倒计时</span>
        <div class="slack-header-right">
          <button
            ref="timePill"
            type="button"
            class="time-pill"
            aria-haspopup="dialog"
            title="修改下班时间"
            @click.stop="openWorkEndEditor"
            @pointerdown.stop
            @mousedown.stop
            @touchstart.stop
          >
            <span>下班</span>&nbsp;<span>{{ currentWorkEnd }}</span>
          </button>
          <span class="slack-badge">{{ offWork.badge }}</span>
        </div>
      </div>
      <div class="slack-time-value">
        {{ offWork.headline }}
      </div>
      <div class="slack-subtext">
        {{ offWork.subtext }}
      </div>
      <div class="slack-progress-track">
        <div
          class="slack-progress-bar"
          :style="{ width: `${offWork.progress}%` }"
        />
      </div>
    </div>

    <div class="slack-metrics">
      <div class="metric-card">
        <div class="metric-label">
          {{ payday.isToday ? '发薪日' : '距发薪日' }}
          <span v-if="payday.adjustedNote" class="metric-tag">{{ payday.adjustedNote }}</span>
        </div>
        <div class="metric-value">
          <template v-if="payday.isToday">
            今天发薪
          </template>
          <template v-else>
            {{ payday.daysLeft }}<span class="metric-unit">天</span>
          </template>
        </div>
        <div class="metric-foot">
          {{ payday.dateText }}
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-label">
          {{ holiday.covered ? holiday.name : '下个假期' }}
        </div>
        <div class="metric-value" :class="{ 'is-notice': !holiday.covered }">
          <template v-if="!holiday.covered">
            待更新
          </template>
          <template v-else-if="holiday.inHoliday">
            放假中
          </template>
          <template v-else>
            {{ holiday.daysLeft }}<span class="metric-unit">天</span>
          </template>
        </div>
        <div class="metric-foot">
          {{ holiday.covered ? `${holiday.dateText} · ${holiday.notice}` : holiday.notice }}
        </div>
      </div>
    </div>

    <Teleport to="body">
      <dialog ref="workEndEditor" class="work-end-editor" aria-label="编辑下班时间" @close="timePill?.focus()">
        <form class="work-end-form" @submit.prevent="saveWorkEnd">
          <label>
            <span>下班时间</span>
            <input v-model="draftWorkEnd" type="time" step="60" required autofocus>
          </label>
          <div class="work-end-actions">
            <button type="button" class="btn" @click="workEndEditor?.close()">取消</button>
            <button type="submit" class="btn btn-primary">保存</button>
          </div>
        </form>
      </dialog>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, onUnmounted, ref } from 'vue'
import { useStore } from '@/store'
import {
  calcNextHoliday,
  calcOffWorkState,
  calcPaydayCountdown,
  type RestMode
} from './holidays'

export default defineComponent({
  name: 'SlackCountdown',
  props: {
    element: {
      type: Object,
      default: () => ({})
    },
    componentSetting: {
      type: Object,
      required: true
    }
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

    const currentWorkEnd = computed(() => props.componentSetting.workEnd || '18:00')
    const timePill = ref<HTMLButtonElement>()
    const workEndEditor = ref<HTMLDialogElement>()
    const draftWorkEnd = ref('')

    /** 整颗标签打开同一个编辑框；每次打开以已保存的值作为草稿。 */
    const openWorkEndEditor = () => {
      if (!props.element?.i || !workEndEditor.value || workEndEditor.value.open) return
      draftWorkEnd.value = currentWorkEnd.value
      workEndEditor.value.showModal()
    }

    /** 只保存有效的 24 小时时间，取消或按 Esc 不写入配置。 */
    const saveWorkEnd = () => {
      const value = draftWorkEnd.value
      if (!props.element?.i || !/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value)) return
      const nextElement = JSON.parse(JSON.stringify(props.element))
      nextElement.componentSetting = {
        ...(nextElement.componentSetting || {}),
        workEnd: value
      }
      store.editComponent(nextElement)
      workEndEditor.value?.close()
    }

    const restMode = computed<RestMode>(() =>
      props.componentSetting.restMode === 'single' ? 'single' : 'double'
    )

    const offWork = computed(() =>
      calcOffWorkState(
        now.value,
        props.componentSetting.workStart || '09:00',
        currentWorkEnd.value,
        restMode.value
      )
    )

    const payday = computed(() =>
      calcPaydayCountdown(
        now.value,
        Number(props.componentSetting.paydayDay) || 15,
        props.componentSetting.advanceOnRest !== false,
        restMode.value
      )
    )

    const holiday = computed(() => calcNextHoliday(now.value))

    return {
      currentWorkEnd,
      timePill,
      workEndEditor,
      draftWorkEnd,
      openWorkEndEditor,
      saveWorkEnd,
      offWork,
      payday,
      holiday
    }
  }
})
</script>

<style lang="scss" scoped>
.slack-countdown-wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  padding: var(--slack-padding, 18px);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 12px;
  overflow: hidden;
}

// 解锁时网格和固定组件会出现右上角的编辑按钮，给时间按钮留出独立点击区域。
:global(.card-edit-overlay + .slack-countdown-wrapper) {
  padding-top: max(var(--slack-padding, 18px), 42px);
}

.slack-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 6px;
}

.slack-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.slack-title {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.03em;
  opacity: 0.9;
  white-space: nowrap;
  flex-shrink: 0;
}

.time-pill {
  display: inline-flex;
  align-items: center;
  appearance: none;
  color: inherit;
  font-family: inherit;
  font-variant-numeric: tabular-nums;
  font-size: 11px;
  padding: 2px 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.22);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 0.18s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.25);
  }

  &:focus-visible {
    outline: 2px solid #409eff;
    outline-offset: 2px;
  }
}

.work-end-editor {
  box-sizing: border-box;
  width: min(320px, calc(100vw - 32px));
  padding: 20px;
  color: #0f172a;
  background: #fff;
  border: 1px solid #dbe4ef;
  border-radius: 14px;

  &::backdrop { background: rgba(15, 23, 42, 0.48); }
}

.work-end-form label {
  display: grid;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;

  input {
    box-sizing: border-box;
    width: 100%;
    min-width: 0;
    min-height: 44px;
    padding: 6px 10px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background: #fff;
    color: #0f172a;
    font: inherit;
    font-size: 16px;
  }
}

.work-end-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;

  .btn { min-height: 44px; }
}

.slack-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.16);
  opacity: 0.9;
  white-space: nowrap;
  flex-shrink: 0;
}

.slack-time-value {
  margin-top: 6px;
  font-size: clamp(24px, 2.6vw, 32px);
  font-weight: 700;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.slack-subtext {
  margin-top: 4px;
  font-size: 12px;
  opacity: 0.78;
}

.slack-progress-track {
  margin-top: 10px;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  overflow: hidden;
}

.slack-progress-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #60a5fa 0%, #34d399 100%);
  transition: width 0.6s ease;
}

.slack-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.metric-card {
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.09);
  border: 1px solid rgba(255, 255, 255, 0.12);
  min-width: 0;
}

.metric-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  opacity: 0.84;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.metric-tag {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 999px;
  background: rgba(52, 211, 153, 0.22);
  color: #a7f3d0;
  flex-shrink: 0;
}

.metric-value {
  margin-top: 4px;
  font-size: 19px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.25;
  white-space: nowrap;

  &.is-notice {
    font-size: 15px;
    opacity: 0.9;
  }
}

.metric-unit {
  font-size: 12px;
  font-weight: 500;
  margin-left: 3px;
  opacity: 0.8;
}

.metric-foot {
  margin-top: 3px;
  font-size: 11px;
  opacity: 0.72;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
