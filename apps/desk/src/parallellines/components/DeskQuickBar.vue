<template>
  <div class="desk-quick-bar" @click.stop>
    <!-- 云同步状态胶囊 -->
    <button
      type="button"
      class="quick-pill sync-pill"
      :class="`sync-${cloudSyncState.status}`"
      :title="cloudSyncState.message"
      @click="showSyncDialog = true; showThemePanel = false; showCatalogDialog = false"
    >
      <span>{{ syncIcon }}</span>
      <span class="pill-text">{{ syncLabel }}</span>
    </button>

    <button
      type="button"
      class="quick-pill"
      :class="{ active: !isLock }"
      :title="isLock ? '解锁以拖拽或调整组件大小' : '点击锁定布局'"
      @click="toggleLock"
    >
      <span>{{ isLock ? '🔒' : '🔓' }}</span>
      <span class="pill-text">{{ isLock ? '编辑' : '锁定' }}</span>
    </button>

    <button
      type="button"
      class="quick-pill"
      title="切换工作台主题配色"
      @click="showThemePanel = !showThemePanel; showCatalogDialog = false"
    >
      <span>🎨</span>
      <span class="pill-text">主题</span>
    </button>

    <button
      type="button"
      class="quick-pill"
      title="一键添加平行线单个游戏或工具到桌面"
      @click="showCatalogDialog = true; showThemePanel = false"
    >
      <span>📌</span>
      <span class="pill-text">快捷库</span>
    </button>

    <button
      type="button"
      class="quick-pill"
      title="添加工作台组件"
      aria-label="添加组件"
      @click="$emit('add-component')"
    >
      <span>＋</span>
      <span class="pill-text">组件</span>
    </button>

    <!-- 极简主题切换浮层 -->
    <transition name="quick-fade">
      <div v-if="showThemePanel" class="theme-popover" @click.stop>
        <div class="popover-title">选择默认主题氛围</div>
        <div class="theme-grid">
          <button
            v-for="theme in themes"
            :key="theme.id"
            type="button"
            class="theme-swatch"
            @click="applyTheme(theme)"
          >
            <span class="swatch-preview" :style="{ background: theme.background }" />
            <span class="swatch-name">{{ theme.name }}</span>
          </button>
        </div>
      </div>
    </transition>

    <!-- 平行线单个游戏 / 工具快捷库弹窗 -->
    <easy-dialog
      v-model="showCatalogDialog"
      title="添加平行线单项快捷入口"
      width="min(560px, 94vw)"
      height="min(480px, 86vh)"
    >
      <div class="catalog-body">
        <div class="catalog-tabs">
          <button
            v-for="tab in catalogTabs"
            :key="tab.key"
            type="button"
            class="catalog-tab"
            :class="{ active: activeCatalogTab === tab.key }"
            @click="activeCatalogTab = tab.key"
          >
            {{ tab.label }}
          </button>
        </div>

        <div class="catalog-grid">
          <div
            v-for="entry in currentCatalogItems"
            :key="entry.url"
            class="catalog-item"
          >
            <span class="catalog-icon" :style="{ background: entry.color }">{{ entry.icon }}</span>
            <div class="catalog-info">
              <div class="catalog-name">{{ entry.title }}</div>
              <div class="catalog-desc">{{ entry.desc }}</div>
            </div>
            <button
              type="button"
              class="catalog-pin-btn"
              :disabled="isPinned(entry.url)"
              @click="pinEntry(entry)"
            >
              {{ isPinned(entry.url) ? '已添加' : '＋ 固定' }}
            </button>
          </div>
        </div>
      </div>
    </easy-dialog>

    <!-- 云同步与冲突处理弹窗 -->
    <easy-dialog
      v-model="showSyncDialog"
      title="工作台云同步"
      width="min(460px, 94vw)"
      height="min(340px, 84vh)"
    >
      <div class="sync-dialog-body">
        <div class="sync-status-card" :class="`is-${cloudSyncState.status}`">
          <div class="sync-status-title">{{ syncLabel }}</div>
          <div class="sync-status-desc">{{ cloudSyncState.message }}</div>
          <div v-if="cloudSyncState.username" class="sync-meta">
            当前账号：{{ cloudSyncState.username }} · {{ cloudSyncState.status === 'conflict' ? '本地基准版本' : '云端版本' }} v{{ cloudSyncState.revision }}
          </div>
        </div>

        <p class="sync-privacy-note">
          云同步仅保存你的布局、主题、书签与明确保存的 AI 快捷指令；本地图片、待办正文、笔记正文、天气城市与闹钟条目仅留在本地浏览器。
        </p>

        <div class="sync-actions">
          <template v-if="cloudSyncState.status === 'guest' || cloudSyncState.status === 'account_changed'">
            <a href="/auth?redirect=/desk/" class="sync-btn primary">前往主站登录</a>
            <button type="button" class="sync-btn" @click="handleRecheckSync">重新检测登录态</button>
          </template>

          <button
            v-else-if="!cloudSyncState.userId || cloudSyncState.status === 'checking'"
            type="button"
            class="sync-btn"
            :disabled="cloudSyncState.status === 'checking'"
            @click="handleRecheckSync"
          >
            重新检测登录态
          </button>

          <template v-else-if="cloudSyncState.status === 'needs_first_upload'">
            <button type="button" class="sync-btn primary" @click="handleFirstUpload">
              确认上传当前本地布局到云端
            </button>
            <button type="button" class="sync-btn" @click="showSyncDialog = false">
              暂不同步（继续本地）
            </button>
          </template>

          <template v-else-if="cloudSyncState.status === 'conflict'">
            <button type="button" class="sync-btn primary" @click="handlePullLatest">
              采用云端最新版本（v{{ cloudSyncState.conflictRevision || '最新' }}）
            </button>
            <button type="button" class="sync-btn danger" @click="handleForceOverwriteCloud">
              保留当前本地布局并覆盖云端
            </button>
          </template>

          <template v-else>
            <button
              type="button"
              class="sync-btn primary"
              :disabled="cloudSyncState.status === 'saving'"
              @click="handleManualPush"
            >
              {{ cloudSyncState.status === 'saving' ? '同步中...' : '立即同步到云端' }}
            </button>
            <button type="button" class="sync-btn" @click="handlePullLatest">
              拉取云端最新版本
            </button>
          </template>
        </div>
      </div>
    </easy-dialog>
  </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElNotification } from 'element-plus'
import { useStore } from '@/store'
import { uid } from '@/utils'
import {
  cloudSyncState,
  initCloudSync,
  pullLatestCloudConfig,
  pushCloudConfig,
} from '@/parallellines/cloudSync'

defineEmits(['add-component'])

const store = useStore()
const isLock = computed(() => store.isLock)
const showThemePanel = ref(false)
const showCatalogDialog = ref(false)
const showSyncDialog = ref(false)
const activeCatalogTab = ref<'games' | 'tools' | 'sites'>('games')

const syncIcon = computed(() => {
  switch (cloudSyncState.status) {
    case 'synced':
      return '☁'
    case 'saving':
    case 'checking':
      return '↻'
    case 'conflict':
    case 'too_large':
    case 'error':
      return '⚠'
    case 'needs_first_upload':
      return '⬆'
    default:
      return '☁'
  }
})

const syncLabel = computed(() => {
  switch (cloudSyncState.status) {
    case 'guest':
    case 'account_changed':
      return '本地模式'
    case 'checking':
      return '检查中'
    case 'needs_first_upload':
      return '待首次同步'
    case 'synced':
      return `已同步 v${cloudSyncState.revision}`
    case 'dirty':
      return '待保存'
    case 'saving':
      return '同步中'
    case 'conflict':
      return '云端冲突'
    case 'too_large':
      return '超 128KB'
    case 'offline':
      return '离线本地'
    case 'error':
      return '同步异常'
    default:
      return '本地模式'
  }
})

const handleRecheckSync = async () => {
  await initCloudSync(store)
}

const handleFirstUpload = async () => {
  const ok = await pushCloudConfig(store, '0')
  if (ok) {
    ElNotification({ title: '云同步已开启', type: 'success', message: '工作台布局已首次保存到云端' })
    showSyncDialog.value = false
  }
}

const handleManualPush = async () => {
  const ok = await pushCloudConfig(store)
  if (ok) {
    ElNotification({ title: '同步成功', type: 'success', message: `已保存到云端 v${cloudSyncState.revision}` })
  }
}

const handlePullLatest = async () => {
  const ok = await pullLatestCloudConfig(store)
  if (ok) {
    ElNotification({ title: '已更新', type: 'success', message: '已载入云端最新布局，本地待办与笔记已保留' })
    showSyncDialog.value = false
  }
}

const handleForceOverwriteCloud = async () => {
  if (!cloudSyncState.conflictRevision) {
    await initCloudSync(store)
    return
  }
  const ok = await pushCloudConfig(store, cloudSyncState.conflictRevision)
  if (ok) {
    ElNotification({ title: '已覆盖保存', type: 'success', message: `已以本地布局更新至云端 v${cloudSyncState.revision}` })
    showSyncDialog.value = false
  }
}

interface ThemePreset {
  id: string
  name: string
  background: string
}

const themes: ThemePreset[] = [
  {
    id: 'aurora-night',
    name: '极光深海',
    background:
      'radial-gradient(ellipse at 20% 18%, rgba(56, 189, 248, 0.28), transparent 50%), radial-gradient(ellipse at 82% 22%, rgba(99, 102, 241, 0.26), transparent 48%), radial-gradient(ellipse at 50% 95%, rgba(20, 184, 166, 0.22), transparent 55%), linear-gradient(160deg, #0b1220 0%, #162238 52%, #132c33 100%)',
  },
  {
    id: 'nordic-mist',
    name: '北欧晨雾',
    background:
      'radial-gradient(circle at 22% 20%, rgba(147, 197, 253, 0.35), transparent 48%), radial-gradient(circle at 80% 78%, rgba(167, 243, 208, 0.24), transparent 52%), linear-gradient(145deg, #1e293b 0%, #334155 55%, #1e3a5f 100%)',
  },
  {
    id: 'dusk-amber',
    name: '落日余晖',
    background:
      'radial-gradient(circle at 78% 18%, rgba(251, 146, 60, 0.32), transparent 46%), radial-gradient(circle at 18% 82%, rgba(192, 132, 252, 0.24), transparent 52%), linear-gradient(155deg, #1c1917 0%, #3b2434 54%, #27272a 100%)',
  },
  {
    id: 'forest-jade',
    name: '玉青林间',
    background:
      'radial-gradient(circle at 25% 18%, rgba(52, 211, 153, 0.26), transparent 48%), radial-gradient(circle at 80% 80%, rgba(45, 212, 191, 0.2), transparent 50%), linear-gradient(155deg, #0c1f1a 0%, #16372f 52%, #1e293b 100%)',
  },
  {
    id: 'graphite-pure',
    name: '静谧石墨',
    background:
      'radial-gradient(circle at 50% 0%, rgba(148, 163, 184, 0.16), transparent 52%), linear-gradient(180deg, #111827 0%, #18181b 100%)',
  },
]

interface CatalogEntry {
  title: string
  desc: string
  url: string
  icon: string
  color: string
  category: 'games' | 'tools' | 'sites'
}

const catalogItems: CatalogEntry[] = [
  {
    title: '蛇蛇出洞',
    desc: '益智解谜小游戏，顺序放走彩色小蛇',
    url: 'https://pingxingxian.space/play/snake-escape',
    icon: '蛇',
    color: '#10b981',
    category: 'games',
  },
  {
    title: '将军战小兵',
    desc: '经典人机策略棋盘对弈',
    url: 'https://pingxingxian.space/play/generals-soldiers',
    icon: '将',
    color: '#ef4444',
    category: 'games',
  },
  {
    title: '游戏目录',
    desc: '平行线全站小游戏与目录合集',
    url: 'https://pingxingxian.space/games',
    icon: '游',
    color: '#2563eb',
    category: 'games',
  },
  {
    title: 'Excel 公式速查',
    desc: '常用函数公式教程与在线演示',
    url: 'https://pingxingxian.space/tools/excel-formulas',
    icon: '表',
    color: '#16a34a',
    category: 'tools',
  },
  {
    title: '拼豆图纸工具',
    desc: '图片一键转拼豆色号图纸',
    url: 'https://pingxingxian.space/tools/bead-pattern',
    icon: '豆',
    color: '#ec4899',
    category: 'tools',
  },
  {
    title: '列表对比工具',
    desc: '快速核对两份名单/数据的交集与差异',
    url: 'https://pingxingxian.space/tools/list-compare',
    icon: '比',
    color: '#0284c7',
    category: 'tools',
  },
  {
    title: '全部在线工具',
    desc: 'PDF / 音视频 / 图片 / 文本本地工具箱',
    url: 'https://tools.pingxingxian.space/',
    icon: '工',
    color: '#d97706',
    category: 'tools',
  },
  {
    title: '圈子社区',
    desc: '平行线公开版块与成员讨论',
    url: 'https://forum.pingxingxian.space/',
    icon: '圈',
    color: '#059669',
    category: 'sites',
  },
  {
    title: '个人 AI 聊天',
    desc: '多模型对话与个人连接',
    url: 'https://chat.pingxingxian.space/',
    icon: 'AI',
    color: '#7c3aed',
    category: 'sites',
  },
  {
    title: '多人聊天频道',
    desc: '端到端加密多人聊天与角色互动',
    url: 'https://tavern.pingxingxian.space/',
    icon: '聊',
    color: '#db2777',
    category: 'sites',
  },
  {
    title: '模型额度中心',
    desc: '查看钱包余额与调用计费',
    url: 'https://api.pingxingxian.space/',
    icon: '额',
    color: '#0ea5e9',
    category: 'sites',
  },
]

const catalogTabs = [
  { key: 'games' as const, label: '单项游戏' },
  { key: 'tools' as const, label: '单项工具' },
  { key: 'sites' as const, label: '平行线频道' },
]

const currentCatalogItems = computed(() =>
  catalogItems.filter((item) => item.category === activeCatalogTab.value)
)

const bookmarkComponent = computed(() =>
  (store.list || []).find((item: any) => item?.material === 'Bookmark')
)

const isPinned = (url: string) => {
  const list: any[] = bookmarkComponent.value?.componentSetting?.bookmark || []
  return list.some((b: any) => b?.url === url)
}

const pinEntry = (entry: CatalogEntry) => {
  if (!bookmarkComponent.value) {
    ElNotification({
      title: '提示',
      type: 'warning',
      message: '请先在工作台添加「书签导航」组件',
    })
    return
  }
  if (isPinned(entry.url)) return
  const nextComp = JSON.parse(JSON.stringify(bookmarkComponent.value))
  if (!Array.isArray(nextComp.componentSetting.bookmark)) {
    nextComp.componentSetting.bookmark = []
  }
  nextComp.componentSetting.bookmark.push({
    id: `pin-${uid()}`,
    title: entry.title,
    url: entry.url,
    iconType: 'text',
    iconText: entry.icon,
    bgColor: entry.color,
    iconPath: '#ffffff',
    type: 'icon',
  })
  store.editComponent(nextComp)
  ElNotification({
    title: '已固定',
    type: 'success',
    message: `「${entry.title}」已添加到工作台书签栏`,
  })
}

const toggleLock = () => {
  store.updateIsLock(!isLock.value)
}

const applyTheme = (theme: ThemePreset) => {
  store.updateGlobalKey({ key: 'background', value: theme.background })
  showThemePanel.value = false
}

const handleOutsideClick = () => {
  showThemePanel.value = false
}

onMounted(() => window.addEventListener('click', handleOutsideClick))
onUnmounted(() => window.removeEventListener('click', handleOutsideClick))
</script>

<style lang="scss" scoped>
.desk-quick-bar {
  position: fixed;
  top: 14px;
  right: 16px;
  z-index: 120;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow:
    0 12px 32px rgba(2, 6, 23, 0.34),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.quick-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
  color: rgba(248, 250, 252, 0.88);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.18s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.18s ease, color 0.18s ease;

  &:hover,
  &.active {
    background: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.22);
    color: #fff;
  }

  &.sync-conflict,
  &.sync-too_large,
  &.sync-error {
    background: rgba(239, 68, 68, 0.32);
    border-color: rgba(248, 113, 113, 0.65);
    color: #fee2e2;
  }

  &.sync-needs_first_upload {
    background: rgba(59, 130, 246, 0.32);
    border-color: rgba(96, 165, 250, 0.65);
    color: #dbeafe;
  }

  &.sync-synced {
    border-color: rgba(52, 211, 153, 0.45);
  }
}

.sync-dialog-body {
  padding: 6px 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sync-status-card {
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;

  &.is-conflict,
  &.is-too_large,
  &.is-error {
    background: #fef2f2;
    border-color: #fecaca;
  }

  &.is-synced {
    background: #ecfdf5;
    border-color: #a7f3d0;
  }
}

.sync-status-title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
}

.sync-status-desc {
  margin-top: 4px;
  font-size: 13px;
  color: #475569;
  line-height: 1.5;
}

.sync-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
}

.sync-privacy-note {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #64748b;
}

.sync-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sync-btn {
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #334155;
  font-size: 13px;
  font-weight: 500;
  text-decoration: none;
  cursor: pointer;

  &.primary {
    background: #2563eb;
    border-color: #2563eb;
    color: #fff;
  }

  &.danger {
    background: #ef4444;
    border-color: #ef4444;
    color: #fff;
  }

  &:disabled {
    opacity: 0.6;
    cursor: default;
  }
}

.theme-popover {
  position: fixed;
  top: 56px;
  right: 14px;
  width: 248px;
  max-width: calc(100vw - 28px);
  z-index: 130;
  padding: 12px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.92);
  backdrop-filter: blur(22px);
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.38);
  color: #f8fafc;
}

.popover-title {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.82;
  margin-bottom: 10px;
}

.theme-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.theme-swatch {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 5px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
  font-size: 11px;
  cursor: pointer;
  text-align: center;

  &:hover {
    border-color: rgba(255, 255, 255, 0.4);
    background: rgba(255, 255, 255, 0.14);
  }
}

.swatch-preview {
  width: 100%;
  height: 36px;
  border-radius: 7px;
  display: block;
}

.catalog-body {
  padding: 4px 12px 14px;
}

.catalog-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}

.catalog-tab {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #475569;
  font-size: 13px;
  cursor: pointer;

  &.active {
    background: #2563eb;
    border-color: #2563eb;
    color: #fff;
    font-weight: 600;
  }
}

.catalog-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.catalog-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
}

.catalog-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.catalog-info {
  flex: 1;
  min-width: 0;
}

.catalog-name {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.catalog-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.catalog-pin-btn {
  padding: 6px 12px;
  border-radius: 999px;
  border: none;
  background: #2563eb;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;

  &:disabled {
    background: #cbd5e1;
    color: #64748b;
    cursor: default;
  }
}

.quick-fade-enter-active,
.quick-fade-leave-active {
  transition: opacity 0.16s ease, transform 0.16s ease;
}

.quick-fade-enter-from,
.quick-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

@media (max-width: 640px) {
  .desk-quick-bar {
    top: 10px;
    left: 10px;
    right: 10px;
    justify-content: flex-end;
    overflow-x: auto;
    scrollbar-width: none;
    &::-webkit-scrollbar {
      display: none;
    }
  }

  .quick-pill {
    height: 34px;
    padding: 0 10px;
    font-size: 11px;
    white-space: nowrap;
    flex-shrink: 0;
  }
}

@media (max-width: 340px) {
  .pill-text {
    display: none;
  }
}
</style>
