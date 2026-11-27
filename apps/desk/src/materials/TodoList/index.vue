<template>
  <div
    class="todo-list-card material-todolist"
    :style="{
      '--themeColor': componentSetting.themeColor,
      '--themeLightColor': themeLightColor,
      fontSize: componentSetting.baseFontSize + 'px',
      padding: componentSetting.padding + 'px'
    }"
    @contextmenu="contextmenu"
  >
    <div class="head">
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
        <span>{{ formatterDate }} · {{ weekDay }}</span>
        <span aria-hidden="true">⌄</span>
      </button>
    </div>
    <ul class="list">
      <li v-for="(item, index) in todoList" :key="item.content + index" class="list-item">
        <input type="checkbox" name="todo" :checked="item.isChecked">
        <div v-if="!item.isEditing" class="text" @click="handleChecked(index)">
          {{ item.content }}
        </div>
        <input
          v-else
          v-focus
          type="text"
          class="edit"
          :value="editingValue"
          @blur="handleEditSubmit($event, item, index)"
          @keyup.enter="handleEditSubmit($event, item, index)"
        >
        <div v-show="!item.isChecked" class="button" @click="handleChecked(index)" />
        <div v-show="item.isChecked" class="wrapper">
          <svg
            viewBox="0 0 98.5 98.5"
            :width="(20 * componentSetting.baseFontSize) / 16"
            :height="(20 * componentSetting.baseFontSize) / 16"
          >
            <path
              class="checkmark"
              fill="none"
              stroke-width="8"
              stroke-miterlimit="10"
              d="M81.7,17.8C73.5,9.3,62,4,49.2,4C24.3,4,4,24.3,4,49.2s20.3,45.2,45.2,45.2s45.2-20.3,45.2-45.2c0-8.6-2.4-16.6-6.5-23.4l0,0L45.6,68.2L24.7,47.3"
            />
          </svg>
        </div>
        <div class="close" @click.stop="handleRemove(index)">
          <svg
            viewBox="0 0 1024 1024"
            :width="(20 * componentSetting.baseFontSize) / 16"
            :height="(20 * componentSetting.baseFontSize) / 16"
          >
            <path
              d="M510.8096 420.3008l335.296-335.296 90.5088 90.5088-335.296 335.296 335.296 335.296-90.5088 90.5088-335.296-335.296-335.296 335.296-90.5088-90.5088 335.296-335.296-335.296-335.296 90.5088-90.5088z"
            />
          </svg>
        </div>
      </li>
    </ul>
    <button
      type="button"
      class="add"
      :aria-label="$t('新增待办')"
      @click.stop="handleAdd"
      @pointerdown.stop
      @mousedown.stop
      @touchstart.stop
    >
      <svg viewBox="0 0 1024 1024" width="20" height="20">
        <path
          :fill="isDark ? '#fff' : '#464646'"
          d="M510.8096 420.3008l335.296-335.296 90.5088 90.5088-335.296 335.296 335.296 335.296-90.5088 90.5088-335.296-335.296-335.296 335.296-90.5088-90.5088 335.296-335.296-335.296-335.296 90.5088-90.5088z"
        />
      </svg>
    </button>
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
          :todo="componentSetting.todo"
          @select-date="updateDate"
        />
      </dialog>
    </Teleport>
  </div>
</template>

<script lang="ts">
import { ref, computed, defineComponent, ComputedRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useStore } from '@/store'
import DatePicker from './DatePicker.vue'
import dayjs from 'dayjs'
import { lightenDarkenColor, getColorBrightness } from '@/utils/color'
export default defineComponent({
  name: 'TodoList',
  components: {
    DatePicker
  },
  directives: {
    focus(el) {
      if (document.activeElement !== el) el.focus()
    }
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
    const isDark = computed(
      () => getColorBrightness(props.componentSetting.themeColor || '#643a7a') < 150
    )
    const themeLightColor = computed(() =>
      lightenDarkenColor(props.componentSetting.themeColor || '#643a7a', isDark.value ? 50 : -50)
    )

    const date = ref(dayjs().format('YYYY-MM-DD'))
    const dateTrigger = ref<HTMLButtonElement>()
    const calendarDialog = ref<HTMLDialogElement>()
    const calendarOpen = ref(false)
    const editingValue = ref('')
    const todoList: ComputedRef<any[]> = computed(
      () => props.componentSetting.todo[date.value] || []
    )
    const weekDay = computed(() => new Intl.DateTimeFormat(locale.value, { weekday: 'short' })
      .format(dayjs(date.value).toDate()))
    const formatterDate = computed(() => new Intl.DateTimeFormat(locale.value, {
      year: 'numeric', month: 'short', day: 'numeric'
    }).format(dayjs(date.value).toDate()))
    const handleChecked = (index: number) => {
      const isChecked = !todoList.value[index].isChecked
      const element = JSON.parse(JSON.stringify(props.element))
      if (props.isAction) {
        element.actionSetting.actionClickValue.componentSetting.todo[date.value][index].isChecked =
          isChecked
        store.updateActionElement(element)
      } else {
        element.componentSetting.todo[date.value][index].isChecked = isChecked
      }
      store.editComponent(element)
    }
    const handleRemove = (index: number) => {
      const element = JSON.parse(JSON.stringify(props.element))
      if (props.isAction) {
        element.actionSetting.actionClickValue.componentSetting.todo[date.value].splice(index, 1)
        store.updateActionElement(element)
      } else {
        element.componentSetting.todo[date.value].splice(index, 1)
      }
      store.editComponent(element)
    }
    const handleAdd = () => {
      editingValue.value = ''
      const element = JSON.parse(JSON.stringify(props.element))
      const item = {
        content: '',
        isChecked: false,
        isEditing: true
      }
      if (props.isAction) {
        if (!element.actionSetting.actionClickValue.componentSetting.todo[date.value]) {
          element.actionSetting.actionClickValue.componentSetting.todo[date.value] = [item]
        } else {
          element.actionSetting.actionClickValue.componentSetting.todo[date.value].push(item)
        }
        store.updateActionElement(element)
      } else {
        if (!element.componentSetting.todo[date.value]) {
          element.componentSetting.todo[date.value] = [item]
        } else {
          element.componentSetting.todo[date.value].push(item)
        }
      }
      store.editComponent(element)
    }
    const handleEditSubmit = ($event: any, item: any, index: number) => {
      if (item.isEditing) {
        const element = JSON.parse(JSON.stringify(props.element))
        const _item = props.isAction
          ? element.actionSetting.actionClickValue.componentSetting.todo[date.value]
          : element.componentSetting.todo[date.value]
        if ($event.currentTarget.value) {
          _item[index].content = editingValue.value = $event.currentTarget.value
          _item[index].isEditing = false
        } else {
          _item.splice(index, 1)
        }
        if (props.isAction) store.updateActionElement(element)
        store.editComponent(element)
      }
    }

    /** 日期选择与新增待办分开布局；每次打开按已选日期定位月份。 */
    const openCalendar = () => {
      if (!calendarDialog.value || calendarDialog.value.open) return
      calendarOpen.value = true
      calendarDialog.value.showModal()
    }

    const closeCalendar = () => {
      calendarOpen.value = false
      dateTrigger.value?.focus()
    }

    /** 只切换当前待办的日期键，不修改任何一天已保存的内容。 */
    const updateDate = (value: string) => {
      date.value = value
      calendarDialog.value?.close()
    }

    const contextmenu = (e: MouseEvent) => {
      if (store.isLock) {
        e.stopPropagation()
      }
    }

    return {
      weekDay,
      formatterDate,
      todoList,
      handleChecked,
      handleRemove,
      handleAdd,
      handleEditSubmit,
      editingValue,
      dateTrigger,
      calendarDialog,
      calendarOpen,
      openCalendar,
      closeCalendar,
      date,
      updateDate,
      themeLightColor,
      isDark,
      contextmenu
    }
  }
})
</script>
<style scoped lang="scss">
.todo-list-card {
  position: relative;
  box-sizing: border-box;
  display: flex;
  flex-wrap: nowrap;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-height: inherit;
  --themeColor: #643a7a;
  --themeLightColor: #966cac;
  .head {
    flex-shrink: 0;
    display: flex;
    justify-content: center;
    padding-bottom: 8px;
  }
  .date-trigger {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    min-height: 36px;
    max-width: 100%;
    padding: 4px 10px;
    color: inherit;
    font: inherit;
    font-weight: 600;
    border-radius: 8px;
    border: 1px solid rgba(148, 163, 184, 0.5);
    background: rgba(148, 163, 184, 0.12);
    cursor: pointer;
  }
  .list {
    list-style: none;
    padding: 4px 0 10px;
    margin: 0;
    overflow-y: auto;
    min-height: 0;
    flex: 1;
    .list-item {
      position: relative;
      display: flex;
      flex-wrap: nowrap;
      margin: 1em 0;
      padding: 0 10px 0 20px;
      .text {
        flex: 1;
        width: 100%;
        font-size: 1em;
        color: var(--themeColor);
        cursor: pointer;
        transition: color 0.3s ease-in-out;
        user-select: none;
        padding-right: 5px;
      }
      .edit {
        flex: 1;
        width: 100%;
        margin-right: 12px;
        height: 20px;
        font-size: 1em;
        outline: none;
        border: none;
        box-shadow: 0 1px 0 var(--themeLightColor);
        color: var(--themeColor);
        background: transparent;
        border-radius: 0;
      }
      .button {
        z-index: 2;
        box-sizing: border-box;
        width: 1.25em;
        height: 1.25em;
        border: 1px solid var(--themeLightColor);
        border-radius: 50%;
        cursor: pointer;
      }
      .close {
        width: 1.25em;
        height: 1.25em;
        opacity: 0;
        visibility: hidden;
        cursor: pointer;
        margin-left: 4px;
        path {
          fill: var(--themeLightColor);
        }
        &:hover {
          path {
            fill: var(--themeColor);
          }
        }
      }
      &:hover {
        .close {
          visibility: visible;
          animation: closeFadeIn 0.4s forwards;
        }
      }
      .checkmark {
        position: absolute;
        stroke: var(--themeLightColor);
        fill: none;
        stroke-dashoffset: 340;
        stroke-dasharray: 360;
        display: block;
        stroke-width: 8;
        opacity: 0;
      }
      input[type='checkbox'] {
        display: none;
      }
      .wrapper {
        width: 1.25em;
        height: 1.25em;
      }
      input:checked ~ {
        .text {
          color: var(--themeLightColor);
          text-decoration: line-through;
        }
        .wrapper .checkmark {
          animation: dash 0.5s ease-out forwards;
          opacity: 1;
        }
      }
    }
  }
  .add {
    flex: 0 0 44px;
    align-self: center;
    width: 44px;
    height: 44px;
    border: 0;
    margin-top: 6px;
    border-radius: 50%;
    box-shadow: 0 0 10px var(--themeColor);
    background: var(--themeColor);
    transition: box-shadow 0.4s ease-in-out;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: space-around;
    svg {
      transform: rotate(45deg);
    }
    &:hover {
      box-shadow: 0 0 20px var(--themeColor);
      transition: box-shadow 0.4s ease-in-out;
    }
  }
}
.todo-calendar {
  box-sizing: border-box;
  width: min(380px, calc(100vw - 24px));
  max-height: calc(100dvh - 24px);
  padding: 14px;
  overflow: auto;
  border: 1px solid #dbe4ef;
  border-radius: 14px;
  background: #fff;
  color: #0f172a;
  &::backdrop { background: rgba(15, 23, 42, 0.48); }
}
.calendar-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.calendar-close {
  width: 40px;
  height: 40px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #475569;
  font-size: 22px;
  cursor: pointer;
}
@keyframes dash {
  0% {
    stroke-dashoffset: 340;
  }
  100% {
    stroke-dashoffset: 0;
  }
}
@keyframes closeFadeIn {
  0% {
    opacity: 0;
    transform: scale(0.5);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}
</style>

