<template>
  <teleport to="body">
    <transition name="gallery-fade">
      <div
        v-if="modelValue"
        class="widget-studio-backdrop"
        @click.self="$emit('update:modelValue', false)"
      >
        <div
          ref="dialog"
          class="widget-studio-modal"
          role="dialog"
          aria-modal="true"
          aria-labelledby="widget-studio-title"
          @keydown.esc.stop.prevent="emit('update:modelValue', false)"
          @keydown.tab="keepFocusInside"
        >
          <!-- 顶栏 -->
          <div class="studio-header">
            <div class="studio-header-left">
              <h3 id="widget-studio-title" class="studio-title">添加组件</h3>
              <span class="studio-subtitle">选择一个组件，预览后添加到桌面</span>
            </div>
            <button
              type="button"
              class="studio-close-btn"
              aria-label="关闭"
              @click="$emit('update:modelValue', false)"
            >
              ×
            </button>
          </div>

          <!-- 主体左右双栏 -->
          <div class="studio-body">
            <!-- 左侧：组件库 -->
            <aside class="studio-sidebar">
              <div class="sidebar-heading">组件库</div>
              <div class="sidebar-search">
                <span class="search-icon">⌕</span>
                <input
                  ref="searchInput"
                  v-model="searchQuery"
                  type="text"
                  class="search-input"
                  aria-label="搜索组件"
                  placeholder="搜索组件"
                >
              </div>
              <div class="sidebar-list">
                <button
                  v-for="item in filteredCatalog"
                  :key="item.material"
                  type="button"
                  class="sidebar-item"
                  :class="{ active: selectedMaterial === item.material }"
                  :aria-pressed="selectedMaterial === item.material"
                  @click="selectMaterial(item)"
                >
                  <span class="sidebar-item-icon" :style="{ color: item.iconColor }">
                    {{ item.icon }}
                  </span>
                  <span class="sidebar-item-name">{{ item.name }}</span>
                  <span v-if="selectedMaterial === item.material" class="sidebar-check">✓</span>
                </button>
                <div v-if="!filteredCatalog.length" class="search-empty">
                  <span role="status">没有匹配的组件</span>
                  <button class="quiet-btn" type="button" @click="clearSearch">清空搜索</button>
                </div>
              </div>
            </aside>

            <!-- 右侧：实时预览 + 属性分组 -->
            <section class="studio-inspector">
              <div class="inspector-scroll">
                <!-- 实时预览 -->
                <div class="preview-header">
                  <span class="preview-label">实时预览</span>
                  <span class="preview-size-badge">{{ sizeBadgeText }}</span>
                </div>
                <div
                  ref="previewStage"
                  class="preview-stage"
                  role="region"
                  aria-label="组件尺寸预览，可滚动查看"
                  tabindex="0"
                  :style="{ background: desktopBackground }"
                >
                  <div class="preview-card-shell" :style="previewShellStyle">
                    <div class="preview-card-bg" :style="previewBgStyle" />
                    <div class="preview-card-inner" inert>
                      <div v-if="selectedMaterial === 'WeatherCard'" class="preview-sample">
                        <WeatherIcon kind="sun" />
                        <strong>晴 · 24°C</strong>
                        <span>天气示例</span>
                      </div>
                      <div v-else-if="selectedMaterial === 'AlarmTimer'" class="preview-sample">
                        <strong>05:00</strong>
                        <span>定时器示例 · 未启动</span>
                      </div>
                      <component
                        :is="previewComponent"
                        v-else-if="previewComponent"
                        :element="previewElement"
                        :component-setting="draft.componentSetting"
                      />
                    </div>
                  </div>
                </div>

                <!-- 高频首屏配置：定位、尺寸、核心内容 -->
                <div class="inspector-core">
                  <div class="prop-row">
                    <span class="prop-label">定位</span>
                    <div class="segmented-control">
                      <button
                        type="button"
                        class="seg-btn"
                        :class="{ active: draft.position === 1 }"
                          :aria-pressed="draft.position === 1"
                        @click="switchPosition(1)"
                      >
                        栅格
                      </button>
                      <button
                        type="button"
                        class="seg-btn"
                        :class="{ active: draft.position === 2 }"
                          :aria-pressed="draft.position === 2"
                        @click="switchPosition(2)"
                      >
                        固定
                      </button>
                    </div>
                  </div>

                  <div class="prop-row prop-row-size">
                    <span class="prop-label">宽度</span>
                    <div class="size-field">
                      <input
                        v-model.number="draft.w"
                        type="number"
                        class="num-input"
                        aria-label="宽度"
                        :min="sizeBounds.min"
                        :max="sizeBounds.maxWidth"
                      >
                      <span class="unit-text">{{ draft.position === 1 ? 'FR' : 'PX' }}</span>
                    </div>
                    <span class="prop-label prop-label-inline">高度</span>
                    <div class="size-field">
                      <input
                        v-model.number="draft.h"
                        type="number"
                        class="num-input"
                        aria-label="高度"
                        :min="sizeBounds.min"
                        :max="sizeBounds.maxHeight"
                      >
                      <span class="unit-text">{{ draft.position === 1 ? 'FR' : 'PX' }}</span>
                    </div>
                  </div>

                  <!-- 按当前选中组件展示最常用的内容字段 -->
                  <template v-if="selectedMaterial === 'Empty'">
                    <div class="prop-row">
                      <span class="prop-label">自定义文本</span>
                      <input
                        v-model="draft.componentSetting.customText"
                        type="text"
                        class="text-input"
                        aria-label="自定义文本"
                        placeholder="输入展示文本，如：今日重点"
                      >
                    </div>
                  </template>

                  <template v-else-if="selectedMaterial === 'EventCountdown'">
                    <div class="prop-row">
                      <span class="prop-label">事件名称</span>
                      <input
                        v-model="draft.componentSetting.eventName"
                        type="text"
                        class="text-input"
                        placeholder="例如：版本上线 / 考研 / 纪念日"
                      >
                    </div>
                    <div class="prop-row">
                      <span class="prop-label">目标时间</span>
                      <input
                        v-model="draft.componentSetting.targetTime"
                        type="datetime-local"
                        class="text-input"
                      >
                    </div>
                    <div class="prop-row">
                      <span class="prop-label">样式</span>
                      <div class="segmented-control">
                        <button
                          v-for="st in eventCountdownStyles"
                          :key="st.value"
                          type="button"
                          class="seg-btn"
                          :class="{ active: draft.componentSetting.style === st.value }"
                          @click="draft.componentSetting.style = st.value"
                        >
                          {{ st.label }}
                        </button>
                      </div>
                    </div>
                  </template>

                  <template v-else-if="selectedMaterial === 'SlackCountdown'">
                    <div class="prop-row prop-row-size">
                      <span class="prop-label">下班时间</span>
                      <input
                        v-model="draft.componentSetting.workEnd"
                        type="time"
                        class="text-input compact"
                      >
                      <span class="prop-label prop-label-inline">发薪日</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.componentSetting.paydayDay"
                          type="number"
                          class="num-input"
                          min="1"
                          max="31"
                        >
                        <span class="unit-text">号</span>
                      </div>
                    </div>
                  </template>

                  <template v-else-if="selectedMaterial === 'Clock'">
                    <div class="prop-row">
                      <span class="prop-label">字号</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.componentSetting.textFontSize"
                          type="number"
                          class="num-input"
                          min="24"
                          max="140"
                        >
                        <span class="unit-text">PX</span>
                      </div>
                    </div>
                  </template>

                  <template v-else-if="selectedMaterial === 'Day'">
                    <div class="prop-row">
                      <span class="prop-label">日期格式</span>
                      <input
                        v-model="draft.componentSetting.formatter"
                        type="text"
                        class="text-input"
                        placeholder="YYYY-MM-DD"
                      >
                    </div>
                  </template>
                </div>

                <!-- 折叠分组 1：外观 -->
                <div class="accordion-section">
                  <button
                    type="button"
                    class="accordion-trigger"
                    :aria-expanded="appearanceOpen"
                    @click="appearanceOpen = !appearanceOpen"
                  >
                    <span>外观</span>
                    <span class="accordion-arrow" :class="{ open: appearanceOpen }">⌄</span>
                  </button>
                  <div v-if="appearanceOpen" class="accordion-content">
                    <div class="prop-row">
                      <span class="prop-label">背景风格</span>
                      <div class="segmented-control">
                        <button
                          type="button"
                          class="seg-btn"
                          :class="{ active: bgPreset === 'glass' }"
                          @click="applyBgPreset('glass')"
                        >
                          毛玻璃
                        </button>
                        <button
                          type="button"
                          class="seg-btn"
                          :class="{ active: bgPreset === 'transparent' }"
                          @click="applyBgPreset('transparent')"
                        >
                          透明
                        </button>
                        <button
                          type="button"
                          class="seg-btn"
                          :class="{ active: bgPreset === 'dark' }"
                          @click="applyBgPreset('dark')"
                        >
                          深色
                        </button>
                      </div>
                    </div>
                    <div class="prop-row prop-row-size">
                      <span class="prop-label">圆角</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.borderRadius"
                          type="number"
                          class="num-input"
                          aria-label="圆角"
                          min="0"
                          max="100"
                        >
                        <span class="unit-text">PX</span>
                      </div>
                      <span class="prop-label prop-label-inline">文字颜色</span>
                      <input
                        v-model="draft.componentSetting.textColor"
                        type="color"
                        class="color-input"
                      >
                    </div>
                    <div class="prop-row">
                      <span class="prop-label">字体</span>
                      <input
                        v-model="draft.componentSetting.fontFamily"
                        type="text"
                        class="text-input"
                        placeholder="默认跟随系统无衬线字体"
                      >
                    </div>
                  </div>
                </div>

                <!-- 折叠分组 2：高级设置 -->
                <div class="accordion-section">
                  <button
                    type="button"
                    class="accordion-trigger"
                    :aria-expanded="advancedOpen"
                    @click="advancedOpen = !advancedOpen"
                  >
                    <span>高级设置</span>
                    <span class="accordion-arrow" :class="{ open: advancedOpen }">⌄</span>
                  </button>
                  <div v-if="advancedOpen" class="accordion-content">
                    <div class="prop-row prop-row-size">
                      <span class="prop-label">层级</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.zIndex"
                          type="number"
                          class="num-input"
                          aria-label="层级"
                          min="0"
                          max="9999"
                        >
                        <span class="unit-text">Z</span>
                      </div>
                      <span class="prop-label prop-label-inline">内边距</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.componentSetting.padding"
                          type="number"
                          class="num-input"
                          min="0"
                          max="48"
                        >
                        <span class="unit-text">PX</span>
                      </div>
                    </div>
                    <div v-if="draft.position === 2" class="prop-row">
                      <span class="prop-label">固定锚点</span>
                      <select v-model.number="draft.affixInfo.mode" aria-label="固定锚点" class="anchor-select">
                        <option :value="1">左上</option>
                        <option :value="2">右上</option>
                        <option :value="3">左下</option>
                        <option :value="4">右下</option>
                      </select>
                    </div>
                    <div v-if="draft.position === 2" class="prop-row prop-row-size">
                      <span class="prop-label">{{ horizontalOffset }}</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.affixInfo.x"
                          type="number"
                          class="num-input"
                          :aria-label="horizontalOffset"
                        >
                        <span class="unit-text">PX</span>
                      </div>
                      <span class="prop-label prop-label-inline">{{ verticalOffset }}</span>
                      <div class="size-field">
                        <input
                          v-model.number="draft.affixInfo.y"
                          type="number"
                          class="num-input"
                          :aria-label="verticalOffset"
                        >
                        <span class="unit-text">PX</span>
                      </div>
                    </div>
                    <div class="prop-row">
                      <span class="prop-label">自定义 ID</span>
                      <input
                        v-model="draft.customId"
                        type="text"
                        class="text-input"
                        placeholder="可选，留空自动生成"
                      >
                    </div>
                    <button type="button" class="quiet-btn" :disabled="!validDraft" @click="openFullSettings">
                      打开完整配置
                    </button>
                  </div>
                </div>
              </div>

              <!-- 底部固定操作栏 -->
              <div class="studio-footer">
                <span v-if="!validDraft" class="draft-warning" role="status">请检查尺寸、圆角、层级和边距</span>
                <button
                  type="button"
                  class="footer-btn"
                  @click="$emit('update:modelValue', false)"
                >
                  取消
                </button>
                <button
                  type="button"
                  class="footer-btn primary"
                  :disabled="!validDraft"
                  @click="handleAddToDesktop"
                >
                  添加到桌面
                </button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script lang="ts" setup>
import { computed, defineAsyncComponent, nextTick, reactive, ref, watch } from 'vue'
import { ElNotification } from 'element-plus'
import { useStore } from '@/store'
import { uid } from '@/utils'
import SettingMap from '@/materials/setting'
import { MATERIAL_LIST_MAP } from '@/constanst'
import useScreenMode from '@/hooks/useScreenMode'
import WeatherIcon from '@/parallellines/materials/WeatherCard/WeatherIcon.vue'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'open-advanced', draft: ComponentOptions): void
}>()

const store = useStore()
const { windowWidth, windowHeight } = useScreenMode()
const dialog = ref<HTMLElement>()
const searchInput = ref<HTMLInputElement>()
const previewStage = ref<HTMLElement>()
const stageSize = reactive({ width: 0, height: 0 })
let opener: HTMLElement | null = null
let handingOff = false

const PREVIEW_COMPONENTS: Record<string, any> = {
  Clock: defineAsyncComponent(() => import('@/materials/Clock/index.vue')),
  SlackCountdown: defineAsyncComponent(() => import('@/parallellines/materials/SlackCountdown/index.vue')),
  EventCountdown: defineAsyncComponent(() => import('@/parallellines/materials/EventCountdown/index.vue')),
  Search: defineAsyncComponent(() => import('@/materials/Search/index.vue')),
  CountDown: defineAsyncComponent(() => import('@/materials/CountDown/index.vue')),
  Collection: defineAsyncComponent(() => import('@/materials/Collection/index.vue')),
  TodoList: defineAsyncComponent(() => import('@/materials/TodoList/index.vue')),
  Editor: defineAsyncComponent(() => import('@/materials/Editor/index.vue')),
  AiSearch: defineAsyncComponent(() => import('@/parallellines/materials/AiSearch/index.vue')),
  Bookmark: defineAsyncComponent(() => import('@/materials/Bookmark/index.vue')),
  Day: defineAsyncComponent(() => import('@/materials/Day/index.vue')),
  Empty: defineAsyncComponent(() => import('@/materials/Empty/index.vue')),
}

interface CatalogWidget {
  material: string
  name: string
  icon: string
  iconColor: string
  w: number
  h: number
  transparentBg?: boolean
  defaultOverride?: Record<string, any>
}

const featured: CatalogWidget[] = [
  { material: 'Clock', name: '时钟', icon: '◷', iconColor: '#6366f1', w: 6, h: 4, transparentBg: true },
  { material: 'EventCountdown', name: '事件倒计时', icon: '⧗', iconColor: '#0ea5e9', w: 5, h: 6 },
  { material: 'SlackCountdown', name: '下班倒计时', icon: '⌛', iconColor: '#f59e0b', w: 5, h: 7 },
  { material: 'TodoList', name: '备忘清单', icon: '☑', iconColor: '#10b981', w: 5, h: 7 },
  { material: 'WeatherCard', name: '天气', icon: '☁', iconColor: '#3b82f6', w: 5, h: 6 },
  { material: 'AlarmTimer', name: '闹钟与定时', icon: '⏰', iconColor: '#ef4444', w: 5, h: 7 },
  { material: 'Editor', name: '随手便签', icon: '▤', iconColor: '#8b5cf6', w: 5, h: 7 },
  { material: 'AiSearch', name: 'AI 智能搜索', icon: '✦', iconColor: '#4f46e5', w: 10, h: 4, transparentBg: true },
  { material: 'Bookmark', name: '书签导航', icon: '⊞', iconColor: '#0284c7', w: 10, h: 4, transparentBg: true },
  { material: 'Day', name: '日期卡片', icon: '▦', iconColor: '#14b8a6', w: 4, h: 3 },
  {
    material: 'Empty',
    name: '占位区块',
    icon: '⛶',
    iconColor: '#2563eb',
    w: 6,
    h: 2,
    defaultOverride: { customText: '今日重点', textFontSize: 22, textColor: '#f8fafc', position: 5 },
  },
]
// 使用与旧配置页相同的注册表作为可添加范围，保留组件库已有的排序和推荐尺寸。
const catalog: CatalogWidget[] = [
  ...featured,
  ...Object.entries(MATERIAL_LIST_MAP)
    .filter(([material]) => !featured.some(item => item.material === material))
    .map(([material, item]) => ({ material, name: item.text, icon: '▦', iconColor: '#64748b', w: 6, h: 2 })),
]

const eventCountdownStyles = [
  { value: 'flip', label: '翻页' },
  { value: 'minimal', label: '极简' },
  { value: 'progress', label: '进度条' },
  { value: 'ring', label: '圆环' },
]

const searchQuery = ref('')
const selectedMaterial = ref('EventCountdown')
const appearanceOpen = ref(false)
const advancedOpen = ref(false)
const bgPreset = ref<'glass' | 'transparent' | 'dark'>('glass')

const draft = reactive({
  position: 1,
  w: 5,
  h: 6,
  zIndex: 12,
  borderRadius: 16,
  background: 'rgba(255, 255, 255, 0.12)',
  backgroundFilter: 'brightness(1)',
  backdropFilter: 'blur(18px)',
  boxShadow: '0 10px 28px rgba(15, 23, 42, 0.24)',
  customId: '',
  affixInfo: { mode: 1, x: 24, y: 24 },
  componentSetting: {} as Record<string, any>,
})

const sizeBounds = computed(() => draft.position === 1
  ? { min: 1, maxWidth: 12, maxHeight: 24 }
  : { min: 40, maxWidth: 1920, maxHeight: 1920 })
const horizontalOffset = computed(() => [1, 3].includes(draft.affixInfo.mode) ? '距左' : '距右')
const verticalOffset = computed(() => [1, 2].includes(draft.affixInfo.mode) ? '距上' : '距下')

function within(value: number, min: number, max: number) {
  return Number.isInteger(value) && value >= min && value <= max
}

const validDraft = computed(() => {
  const { min, maxWidth, maxHeight } = sizeBounds.value
  return within(draft.w, min, maxWidth) && within(draft.h, min, maxHeight)
    && within(draft.borderRadius, 0, 100) && within(draft.zIndex, 0, 9999)
    && (draft.position === 1 || (Number.isFinite(draft.affixInfo.x) && Number.isFinite(draft.affixInfo.y)))
})

const filteredCatalog = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return catalog
  return catalog.filter(
    (item) => item.name.toLowerCase().includes(q) || item.material.toLowerCase().includes(q)
  )
})

const applyBgPreset = (preset: 'glass' | 'transparent' | 'dark') => {
  bgPreset.value = preset
  if (preset === 'transparent') {
    draft.background = 'transparent'
    draft.backdropFilter = ''
    draft.boxShadow = ''
  } else if (preset === 'dark') {
    draft.background = 'rgba(15, 23, 42, 0.56)'
    draft.backdropFilter = 'blur(20px)'
    draft.boxShadow = '0 12px 30px rgba(15, 23, 42, 0.32)'
  } else {
    draft.background = 'rgba(255, 255, 255, 0.12)'
    draft.backdropFilter = 'blur(18px)'
    draft.boxShadow = '0 10px 28px rgba(15, 23, 42, 0.24)'
  }
}

const selectMaterial = (item: CatalogWidget) => {
  selectedMaterial.value = item.material
  draft.position = 1
  draft.w = item.w
  draft.h = item.h
  draft.zIndex = 12
  draft.borderRadius = 16
  draft.customId = ''
  draft.affixInfo = { mode: 1, x: 24, y: 24 }
  applyBgPreset(item.transparentBg ? 'transparent' : 'glass')

  const settingEntry = (SettingMap as Record<string, any>)[item.material]
  const baseData = settingEntry?.formData
    ? JSON.parse(JSON.stringify(settingEntry.formData))
    : {}
  draft.componentSetting = {
    textColor: '#f8fafc',
    fontFamily: '',
    padding: 16,
    ...baseData,
    ...(item.defaultOverride || {}),
  }
}

/** 沿用栅格转固定定位的默认尺寸规则，倍数与旧添加流程保持一致。 */
function fixedSize(w: number, h: number) {
  return { w: Math.min(640, Math.max(240, w * 64)), h: Math.min(480, Math.max(120, h * 42)) }
}

const switchPosition = (pos: 1 | 2) => {
  if (draft.position === pos) return
  draft.position = pos
  if (pos === 2) {
    const size = fixedSize(draft.w, draft.h)
    draft.w = size.w
    draft.h = size.h
  } else {
    const matched = catalog.find((c) => c.material === selectedMaterial.value)
    draft.w = matched?.w ?? 5
    draft.h = matched?.h ?? 6
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
      handingOff = false
      searchQuery.value = ''
      appearanceOpen.value = false
      advancedOpen.value = false
      const current = catalog.find((c) => c.material === selectedMaterial.value) || catalog[0]
      selectMaterial(current)
      await nextTick()
      if (props.modelValue) searchInput.value?.focus()
    } else if (!handingOff) {
      await nextTick()
      if (!props.modelValue && opener?.isConnected) opener.focus()
    }
  }
)

function clearSearch() {
  searchQuery.value = ''
  searchInput.value?.focus()
}

/** Tab 和 Shift+Tab 只遍历弹窗中可见、可用的控件，跳过只读预览。 */
function keepFocusInside(event: KeyboardEvent) {
  const controls = Array.from(dialog.value?.querySelectorAll<HTMLElement>(
    'button:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex="0"]'
  ) ?? []).filter(el => !el.closest('[inert]') && el.getClientRects().length)
  const first = controls[0]
  const last = controls[controls.length - 1]
  if (event.shiftKey ? document.activeElement === first : document.activeElement === last) {
    event.preventDefault()
    const next = event.shiftKey ? last : first
    next?.focus()
  }
}

watch(previewStage, (stage, _, onCleanup) => {
  if (!stage) return
  // 仅外框变化时更新比例。内容溢出导致滚动条出现，不重新缩放当前卡片。
  const observer = new ResizeObserver(() => {
    const style = getComputedStyle(stage)
    stageSize.width = Math.max(0, stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight))
    stageSize.height = Math.max(0, stage.offsetHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom))
  })
  observer.observe(stage, { box: 'border-box' })
  onCleanup(() => observer.disconnect())
})

const desktopBackground = computed(
  () =>
    store.global.background ||
    'linear-gradient(145deg, #0b1220 0%, #162238 52%, #132c33 100%)'
)

const sizeBadgeText = computed(() =>
  draft.position === 1 ? `${draft.w} × ${draft.h} FR` : `${draft.w} × ${draft.h} PX`
)

const previewComponent = computed(() => PREVIEW_COMPONENTS[selectedMaterial.value] || null)

const previewElement = computed(() => ({
  i: 'preview-only',
  material: selectedMaterial.value,
  position: draft.position,
  w: draft.w,
  h: draft.h,
  borderRadius: draft.borderRadius,
  background: draft.background,
  backdropFilter: draft.backdropFilter,
  componentSetting: draft.componentSetting,
}))

const previewShellStyle = computed(() => {
  // 栅格尺寸沿用桌面 12 列、行高和间距的算法；固定尺寸直接按像素等比缩放。
  const gutter = store.global.gutter ?? 10
  const colWidth = Math.max(1, (windowWidth.value - gutter * 13) / 12)
  const rowHeight = Math.min(40, Math.max(20, windowHeight.value / 27))
  const w = Number(draft.w) > 0 ? Number(draft.w) : 1
  const h = Number(draft.h) > 0 ? Number(draft.h) : 1
  const toWidth = (units: number) => draft.position === 1 ? units * colWidth + (units - 1) * gutter : units
  const toHeight = (units: number) => draft.position === 1 ? units * rowHeight + (units - 1) * gutter : units
  const defaults = catalog.find(item => item.material === selectedMaterial.value) ?? catalog[0]
  const reference = draft.position === 1 ? defaults : fixedSize(defaults.w, defaults.h)
  // 以物料的推荐尺寸定比例，再用同一比例画实际宽、高。超出区域时滚动，不挤窄另一边。
  const scale = Math.min(1, stageSize.width / toWidth(reference.w), stageSize.height / toHeight(reference.h))
  const width = toWidth(w)
  const height = toHeight(h)
  return {
    width: `${width * scale}px`,
    height: `${height * scale}px`,
    borderRadius: `${draft.borderRadius}px`,
    boxShadow: draft.boxShadow,
  }
})

const previewBgStyle = computed(() => ({
  background: draft.background,
  borderRadius: `${draft.borderRadius}px`,
  backdropFilter: draft.backdropFilter,
}))

/** 两个添加入口使用同一份草稿；合法的 0 不得被替换成默认值。 */
function draftPayload(): ComponentOptions {
  return {
    material: selectedMaterial.value,
    position: draft.position,
    x: 1,
    y: 0,
    w: draft.w,
    h: draft.h,
    zIndex: draft.zIndex,
    borderRadius: draft.borderRadius,
    background: draft.background,
    backgroundFilter: draft.backgroundFilter,
    backdropFilter: draft.backdropFilter,
    boxShadow: draft.boxShadow,
    customId: draft.customId.trim(),
    affixInfo: { ...draft.affixInfo },
    componentSetting: JSON.parse(JSON.stringify(draft.componentSetting)),
  }
}

function openFullSettings() {
  if (!validDraft.value) return
  handingOff = true
  emit('open-advanced', draftPayload())
}

const handleAddToDesktop = () => {
  if (!validDraft.value) return
  const current = catalog.find((c) => c.material === selectedMaterial.value)
  const payload = { ...draftPayload(), i: `pl-${uid()}` }
  store.addComponent(payload)
  const destination = payload.position === 1 ? store.list : store.affix
  if (!destination.some(item => item.i === payload.i)) {
    ElNotification({ title: '未能添加组件', type: 'error' })
    return
  }
  if (store.isLock) store.updateIsLock(false)
  emit('update:modelValue', false)
  ElNotification({
    title: '已添加到桌面',
    type: 'success',
    message: `「${current?.name || selectedMaterial.value}」已添加到桌面`,
  })
}
</script>

<style lang="scss" scoped>
.widget-studio-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2200;
  background: rgba(15, 23, 42, 0.52);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  box-sizing: border-box;
}

.widget-studio-modal {
  width: min(860px, 96vw);
  height: min(620px, 88vh);
  display: flex;
  flex-direction: column;
  border-radius: 20px;
  background: #ffffff;
  color: #0f172a;
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.36), 0 4px 16px rgba(15, 23, 42, 0.12);
  overflow: hidden;
}

.studio-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px 16px;
  border-bottom: 1px solid #eef2f6;
  flex-shrink: 0;
}

.studio-header-left {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.studio-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.01em;
}

.studio-subtitle {
  font-size: 13px;
  color: #64748b;
}

.studio-close-btn {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  &:hover {
    background: #f1f5f9;
    color: #0f172a;
  }
}

.studio-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

/* 左侧组件库 */
.studio-sidebar {
  width: 232px;
  flex-shrink: 0;
  background: #f6f9fc;
  border-right: 1px solid #e8eef5;
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  box-sizing: border-box;
}

.sidebar-heading {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  padding: 0 4px;
}

.sidebar-search {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  border-radius: 9px;
  background: #ffffff;
  border: 1px solid #dbe4ef;

  &:focus-within {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12);
  }
}

.search-icon {
  font-size: 14px;
  color: #94a3b8;
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: #0f172a;

  &::placeholder {
    color: #94a3b8;
  }
}

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.search-empty {
  padding: 10px 4px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}

.quiet-btn {
  padding: 5px 8px;
  border: 0;
  border-radius: 6px;
  color: #1d4ed8;
  background: transparent;
  font: inherit;
  cursor: pointer;

  &:hover { background: #e6f0ff; }
  &:disabled { opacity: .5; cursor: not-allowed; }
}

.sidebar-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border-radius: 10px;
  border: none;
  background: transparent;
  color: #334155;
  font-size: 13.5px;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease, color 0.14s ease;

  &:hover {
    background: rgba(59, 130, 246, 0.08);
    color: #0f172a;
  }

  &.active {
    background: #e6f0ff;
    color: #0f172a;
    font-weight: 600;
  }
}

.sidebar-item-icon {
  width: 20px;
  text-align: center;
  font-size: 16px;
  flex-shrink: 0;
}

.sidebar-item-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-check {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #2563eb;
  color: #fff;
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 右侧实时预览与配置 */
.studio-inspector {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.inspector-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px 24px 16px;
}

.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.preview-label {
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
}

.preview-size-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 6px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.preview-stage {
  position: relative;
  height: clamp(158px, 24vh, 210px);
  border-radius: 14px;
  padding: 18px;
  box-sizing: border-box;
  display: flex;
  overflow: auto;
  scrollbar-gutter: stable both-edges;
  margin-bottom: 18px;
}

.preview-card-shell {
  position: relative;
  flex-shrink: 0;
  margin: auto;
  box-sizing: border-box;
  border: 1px solid rgba(255, 255, 255, 0.2);
  overflow: hidden;
  transition: width 0.2s ease, height 0.2s ease, border-radius 0.2s ease;
}

.preview-card-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.preview-card-inner {
  position: relative;
  height: 100%;
  z-index: 1;
  pointer-events: none;
}

.preview-sample {
  box-sizing: border-box;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 4px;
  color: #f8fafc;
  font-size: 12px;

  strong { font-size: 22px; font-variant-numeric: tabular-nums; }
  :deep(svg) { width: 22px; height: 22px; }
}

.inspector-core {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 16px;
}

.prop-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.prop-row-size {
  flex-wrap: wrap;
}

.prop-label {
  width: 72px;
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}

.prop-label-inline {
  width: auto;
  margin-left: 10px;
}

.segmented-control {
  display: inline-flex;
  padding: 2px;
  border-radius: 9px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  gap: 2px;
}

.seg-btn {
  padding: 5px 14px;
  border-radius: 7px;
  border: none;
  background: transparent;
  color: #475569;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.14s ease, color 0.14s ease;

  &.active {
    background: #2563eb;
    color: #ffffff;
    font-weight: 600;
    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.28);
  }
}

.size-field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.num-input {
  width: 76px;
  height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid #dbe4ef;
  background: #ffffff;
  color: #0f172a;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  outline: none;

  &:focus {
    border-color: #3b82f6;
  }
}

.unit-text {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.text-input {
  flex: 1;
  min-width: 0;
  height: 36px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid #dbe4ef;
  background: #ffffff;
  color: #0f172a;
  font-size: 13px;
  outline: none;

  &.compact {
    flex: 0 0 128px;
  }

  &:focus {
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
}

.color-input {
  width: 36px;
  height: 32px;
  padding: 2px;
  border-radius: 8px;
  border: 1px solid #dbe4ef;
  background: #fff;
  cursor: pointer;
}

.anchor-select {
  min-height: 34px;
  padding: 0 8px;
  border: 1px solid #dbe4ef;
  border-radius: 8px;
  background: #fff;
  color: #0f172a;
}

/* 折叠分组 */
.accordion-section {
  border-top: 1px solid #eef2f6;
}

.accordion-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 13px 2px;
  border: none;
  background: transparent;
  color: #1e293b;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;

  &:hover {
    color: #2563eb;
  }
}

.accordion-arrow {
  font-size: 16px;
  color: #64748b;
  transition: transform 0.18s ease;

  &.open {
    transform: rotate(180deg);
  }
}

.accordion-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 2px 0 16px;
}

/* 底部固定栏 */
.studio-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid #eef2f6;
  background: #ffffff;
  flex-shrink: 0;
}

.draft-warning {
  margin-right: auto;
  color: #9a3412;
  font-size: 12px;
}

.footer-btn {
  height: 36px;
  padding: 0 18px;
  border-radius: 9px;
  border: 1px solid #dbe4ef;
  background: #ffffff;
  color: #334155;
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.14s ease, border-color 0.14s ease;

  &:hover {
    background: #f8fafc;
    border-color: #cbd5e1;
  }

  &.primary {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
    font-weight: 600;

    &:hover {
      background: #1d4ed8;
    }
  }

  &:disabled {
    opacity: .55;
    cursor: not-allowed;
  }
}

.gallery-fade-enter-active,
.gallery-fade-leave-active {
  transition: opacity 0.18s ease;

  .widget-studio-modal {
    transition: transform 0.18s ease, opacity 0.18s ease;
  }
}

.gallery-fade-enter-from,
.gallery-fade-leave-to {
  opacity: 0;

  .widget-studio-modal {
    transform: scale(0.97) translateY(6px);
    opacity: 0;
  }
}

@media (max-width: 720px) {
  .studio-body {
    flex-direction: column;
  }

  .studio-sidebar {
    width: 100%;
    max-height: 180px;
    border-right: none;
    border-bottom: 1px solid #e8eef5;
  }

  .studio-footer {
    flex-wrap: wrap;
    padding: 10px 14px;
  }

  .footer-btn { min-height: 44px; }
}

@media (max-width: 540px) {
  // 窄屏让标签和对应输入同行，避免两组尺寸换行后错位。
  .prop-row-size {
    display: grid;
    grid-template-columns: 72px minmax(0, 1fr);
    gap: 8px 12px;
  }

  .prop-label-inline { margin-left: 0; }
}
</style>
