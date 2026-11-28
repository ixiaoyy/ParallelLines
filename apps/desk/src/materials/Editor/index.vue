<template>
  <div
    class="wrapper material-editor"
    :style="{ padding: (componentSetting.padding ?? 16) + 'px' }"
    @contextmenu="contextmenu"
  >
    <div v-if="componentSetting.showTitle !== false" class="editor-header">
      <div class="editor-heading">
        <span class="editor-dot" aria-hidden="true" />
        <span class="title">随手便签</span>
      </div>
      <div class="editor-actions">
        <button type="button" class="editor-pill-btn" @click="onImportMarkdown">导入</button>
        <button type="button" class="editor-pill-btn" @click="onExportMarkdown">导出</button>
      </div>
    </div>
    <Milk
      ref="milkdown"
      :style="{
        fontFamily: componentSetting.fontFamily,
        pointerEvents: isLock ? 'auto' : 'none',
        flex: 1
      }"
      :text-color="componentSetting.textColor"
      :font-size="componentSetting.textFontSize"
      :enable-tooltip="componentSetting.enableTooltip"
      :enable-slash="componentSetting.enableSlash"
      :enable-history="componentSetting.enableHistory"
      :enable-prism="componentSetting.enablePrism"
      :enable-clipboard="componentSetting.enableClipboard"
      :markdown="componentSetting.markdown"
      @change="onChange"
    />
    <input ref="inputFileEl" type="file" accept=".md,.txt,.MD,.TXT" style="display:none">
  </div>
</template>

<script lang="ts" setup>
import { ref, watch, computed, toRaw } from 'vue'
import { useStore } from '@/store'
import { useI18n } from 'vue-i18n'
import Milk from './milkdown/Milk.vue'
import { debounce } from '@/utils'
const props = defineProps({
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
})

const store = useStore()
const { t } = useI18n()

const isLock = computed(() => store.isLock)

const milkdown = ref()
const inputFileEl = ref()

// 如果使用数组监听会触发新旧值一样的回调，因为对象内存已改变
watch(
  () => props.componentSetting.enableTooltip,
  () => milkdown.value.update()
)
watch(
  () => props.componentSetting.enableSlash,
  () => milkdown.value.update()
)
watch(
  () => props.componentSetting.enablePrism,
  () => milkdown.value.update()
)
watch(
  () => props.componentSetting.enableHistory,
  () => milkdown.value.update()
)
watch(
  () => props.componentSetting.enableClipboard,
  () => milkdown.value.update()
)

const _saveMarkdown = (md: string) => {
  const element = JSON.parse(JSON.stringify(toRaw(props.element)))
  if (props.isAction) {
    element.actionSetting.actionClickValue.componentSetting.markdown = md
    store.updateActionElement(element)
  } else {
    element.componentSetting.markdown = md
  }
  store.editComponent(element)
}
const onChange = debounce(_saveMarkdown, 300)

const contextmenu = (e: MouseEvent) => {
  if (isLock.value) {
    e.stopPropagation()
  }
}

const onImportMarkdown = () => {
  inputFileEl.value.onchange = (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) {
      const reader = new FileReader()
      reader.onload = (e) => {
        const md = e.target?.result as string
        if (window.confirm(t('导入会覆盖当前内容，是否继续?'))) {
          onChange(md)
          milkdown.value.update()
        }
      }
      reader.readAsText(file)
    }
  }
  inputFileEl.value.click()
}

const onExportMarkdown = () => {
  const md = props.componentSetting.markdown
  const blob = new Blob([md], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'export.md'
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<style lang="scss" scoped>
.wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  color: #f8fafc;
}
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.09);
  flex-shrink: 0;
}
.editor-heading {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  .editor-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #8b5cf6;
    box-shadow: 0 0 10px rgba(139, 92, 246, 0.7);
  }
  .title {
    font-size: 16px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.01em;
  }
}
.editor-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.editor-pill-btn {
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background: rgba(255, 255, 255, 0.07);
  color: rgba(248, 250, 252, 0.86);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
  &:hover {
    background: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.3);
  }
}
</style>
