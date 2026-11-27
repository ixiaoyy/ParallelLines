import { reactive } from 'vue'
import { isAllowedMaterial, isSafeHttpOrRelativeUrl } from './security'

export const WORKSPACE_SCHEMA_VERSION = 1
export const MAX_SYNC_CONFIG_BYTES = 128 * 1024

export type CloudSyncStatus =
  | 'guest'
  | 'checking'
  | 'needs_first_upload'
  | 'synced'
  | 'dirty'
  | 'saving'
  | 'conflict'
  | 'too_large'
  | 'offline'
  | 'error'

export interface WorkspaceSnapshot {
  revision: string
  schema_version: number
  config: Record<string, any> | null
  updated_at: string | null
}

const DEFAULT_SAFE_BG =
  'radial-gradient(ellipse at 20% 18%, rgba(56, 189, 248, 0.26), transparent 50%), radial-gradient(ellipse at 82% 22%, rgba(99, 102, 241, 0.24), transparent 48%), linear-gradient(160deg, #0b1220 0%, #162238 52%, #132c33 100%)'

const PAINT_FUNCTIONS = new Set([
  'rgb',
  'rgba',
  'hsl',
  'hsla',
  'linear-gradient',
  'radial-gradient',
  'conic-gradient',
  'repeating-linear-gradient',
  'repeating-radial-gradient',
  'repeating-conic-gradient',
  'blur',
  'brightness',
  'contrast',
  'drop-shadow',
  'grayscale',
  'hue-rotate',
  'invert',
  'opacity',
  'saturate',
  'sepia',
])

const STYLE_RE = /^[a-zA-Z0-9 #(),.+%\-]*$/
const FONT_RE = /^[\w ,'"\-]*$/

function isValidStyle(value: unknown): value is string {
  if (typeof value !== 'string' || !STYLE_RE.test(value)) return false
  const fns = value.matchAll(/([a-zA-Z][a-zA-Z0-9-]*) *\(/g)
  for (const m of fns) {
    if (!PAINT_FUNCTIONS.has(m[1].toLowerCase())) return false
  }
  return true
}

function safeStyle(value: unknown, fallback = ''): string {
  return isValidStyle(value) ? value : fallback
}

function safeFont(value: unknown): string {
  return typeof value === 'string' && FONT_RE.test(value) ? value : ''
}

function safeNum(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function safeStr(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function safeBool(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function sanitizeSyncBookmark(raw: any): any | null {
  if (!raw || typeof raw !== 'object' || typeof raw.id !== 'string' || !raw.id.trim()) return null
  const url = typeof raw.url === 'string' && isSafeHttpOrRelativeUrl(raw.url) ? raw.url.trim() : ''
  const out: Record<string, any> = {
    id: raw.id.trim(),
    title: safeStr(raw.title),
    url,
    iconType: 'text',
    bgColor: safeStyle(raw.bgColor, '#2563eb'),
    iconPath: safeStyle(raw.iconPath, '#ffffff'),
    type: raw.type === 'folder' ? 'folder' : 'icon',
  }
  if (Array.isArray(raw.children)) {
    out.children = raw.children.map(sanitizeSyncBookmark).filter(Boolean)
  }
  return out
}

function sanitizeSyncShortcut(raw: any): any | null {
  if (
    !raw ||
    typeof raw !== 'object' ||
    typeof raw.id !== 'string' ||
    !raw.id.trim() ||
    typeof raw.name !== 'string' ||
    typeof raw.prompt !== 'string'
  ) {
    return null
  }
  return {
    id: raw.id.trim(),
    name: raw.name,
    icon: safeStr(raw.icon, raw.name.slice(0, 1)),
    color: safeStyle(raw.color, '#6366f1'),
    prompt: raw.prompt,
    autoSend: safeBool(raw.autoSend, false),
  }
}

function pickTextAppearance(s: any): Record<string, any> {
  const out: Record<string, any> = {}
  if (s.fontFamily !== undefined) out.fontFamily = safeFont(s.fontFamily)
  if (s.padding !== undefined) out.padding = safeNum(s.padding, 10)
  if (s.textColor !== undefined) out.textColor = safeStyle(s.textColor, '#f8fafc')
  if (s.textFontSize !== undefined) out.textFontSize = safeNum(s.textFontSize, 14)
  return out
}

function pickPositionedText(s: any): Record<string, any> {
  const out = pickTextAppearance(s)
  if (s.position !== undefined) out.position = safeNum(s.position, 5)
  if (s.textShadow !== undefined) out.textShadow = safeStyle(s.textShadow, '')
  return out
}

function sanitizeSyncComponentSetting(material: string, raw: any): Record<string, any> {
  const s = raw && typeof raw === 'object' ? raw : {}
  switch (material) {
    case 'Empty':
      return { ...pickPositionedText(s), customText: safeStr(s.customText) }
    case 'Clock':
      return {
        ...pickPositionedText(s),
        duration: safeNum(s.duration, 1000),
        textHollow: safeBool(s.textHollow, false),
        textHollowBg: safeStyle(s.textHollowBg, 'rgba(0,0,0,0)'),
        textHollowBorder: safeNum(s.textHollowBorder, 1),
      }
    case 'Day':
      return {
        ...pickPositionedText(s),
        duration: safeNum(s.duration, 1000),
        formatter: safeStr(s.formatter),
        custom: safeStr(s.custom),
        timeZone: safeStr(s.timeZone),
        chineseWeekDay: safeBool(s.chineseWeekDay, false),
        showTTS1: safeBool(s.showTTS1, false),
        showTTS2: safeBool(s.showTTS2, false),
        ttsFontSize: safeNum(s.ttsFontSize, 14),
      }
    case 'Search':
      return {
        ...pickTextAppearance(s),
        backdropBlur: typeof s.backdropBlur === 'number' ? s.backdropBlur : s.backdropBlur ? 1 : 0,
        boxBackground: safeStyle(s.boxBackground, 'rgba(255, 255, 255, 0.14)'),
        boxRadius: safeNum(s.boxRadius, 12),
        boxShadow: safeStyle(s.boxShadow, ''),
        maxWidth: safeNum(s.maxWidth, 620),
        showTabTips: safeBool(s.showTabTips, true),
        focusBgAnimation: safeBool(s.focusBgAnimation, false),
        autoFocus: safeBool(s.autoFocus, false),
        rememberHistory: safeBool(s.rememberHistory, false),
        linkBookMark: safeBool(s.linkBookMark, false),
      }
    case 'AiSearch':
      return {
        ...pickTextAppearance(s),
        maxWidth: safeNum(s.maxWidth, 720),
        autoSaveSearchToShortcut: safeBool(s.autoSaveSearchToShortcut, false),
        defaultMode: safeStr(s.defaultMode, 'ai'),
        shortcuts: Array.isArray(s.shortcuts)
          ? s.shortcuts.map(sanitizeSyncShortcut).filter(Boolean)
          : [],
      }
    case 'Bookmark':
      return {
        ...pickTextAppearance(s),
        boxSize: safeNum(s.boxSize, 44),
        boxRadius: safeNum(s.boxRadius, 14),
        iconSize: safeNum(s.iconSize, 19),
        tileTitleLines: safeNum(s.tileTitleLines, 1),
        maxWidth: safeNum(s.maxWidth, 960),
        closeClickOutside: safeBool(s.closeClickOutside, true),
        disabledDrag: safeBool(s.disabledDrag, false),
        hiddenAddBtn: safeBool(s.hiddenAddBtn, false),
        folderBg: safeStyle(s.folderBg, 'rgba(15, 23, 42, 0.9)'),
        boxShadow: safeStyle(s.boxShadow, ''),
        jumpType: s.jumpType === 2 ? 2 : 1,
        bookmark: Array.isArray(s.bookmark)
          ? s.bookmark.map(sanitizeSyncBookmark).filter(Boolean)
          : [],
      }
    case 'Collection':
      return {
        ...pickPositionedText(s),
        keyboardMaxWidth: safeNum(s.keyboardMaxWidth, 800),
        keyBackground: safeStyle(s.keyBackground, ''),
        keyBorderRadius: safeNum(s.keyBorderRadius, 8),
        keyGutter: safeNum(s.keyGutter, 8),
      }
    case 'TodoList':
      // 待办正文仅保留在本地，不随布局上传
      return {
        baseFontSize: safeNum(s.baseFontSize, 15),
        padding: safeNum(s.padding, 14),
        themeColor: safeStyle(s.themeColor, '#60a5fa'),
        todo: {},
      }
    case 'Editor':
      // 笔记正文仅保留在本地，不随布局上传
      return {
        ...pickTextAppearance(s),
        enablePrism: safeBool(s.enablePrism, false),
        enableSlash: safeBool(s.enableSlash, true),
        enableTooltip: safeBool(s.enableTooltip, true),
        showTitle: safeBool(s.showTitle, true),
        markdown: '',
      }
    case 'CountDown':
      return {
        ...pickPositionedText(s),
        eventName: safeStr(s.eventName),
        eventTime: safeStr(s.eventTime),
        unit: safeStr(s.unit, '小时'),
      }
    case 'SlackCountdown':
      return {
        ...pickTextAppearance(s),
        workStart: safeStr(s.workStart, '09:00'),
        workEnd: safeStr(s.workEnd, '18:00'),
        restMode: safeStr(s.restMode, 'double'),
        paydayDay: safeNum(s.paydayDay, 15),
        advanceOnRest: safeBool(s.advanceOnRest, true),
      }
    case 'WeatherCard':
      // 城市位置仅保留在本地
      return {}
    case 'AlarmTimer':
      // 闹钟条目仅保留在本地
      return {
        fontFamily: safeFont(s.fontFamily),
        textColor: safeStyle(s.textColor, '#f8fafc'),
      }
    default:
      return {}
  }
}

function sanitizeSyncElement(raw: any): any | null {
  if (!raw || typeof raw !== 'object' || typeof raw.i !== 'string' || !raw.i.trim()) return null
  if (!isAllowedMaterial(raw.material)) return null
  const out: Record<string, any> = {
    i: raw.i.trim(),
    material: raw.material,
    position: safeNum(raw.position, 1),
    w: safeNum(raw.w, 4),
    h: safeNum(raw.h, 4),
    x: safeNum(raw.x, 0),
    y: safeNum(raw.y, 0),
    zIndex: safeNum(raw.zIndex, 10),
    borderRadius: safeNum(raw.borderRadius, 16),
    background: safeStyle(raw.background, 'rgba(255, 255, 255, 0.1)'),
    backgroundFilter: safeStyle(raw.backgroundFilter, 'brightness(1)'),
    backdropFilter: safeStyle(raw.backdropFilter, ''),
    boxShadow: safeStyle(raw.boxShadow, ''),
    componentSetting: sanitizeSyncComponentSetting(raw.material, raw.componentSetting),
  }
  if (raw.affixInfo && typeof raw.affixInfo === 'object') {
    out.affixInfo = {
      mode: safeNum(raw.affixInfo.mode, 1),
      x: safeNum(raw.affixInfo.x, 10),
      y: safeNum(raw.affixInfo.y, 10),
    }
  }
  return out
}

function sanitizeSyncGlobal(raw: any): Record<string, any> {
  const g = raw && typeof raw === 'object' ? raw : {}
  return {
    background: safeStyle(g.background, DEFAULT_SAFE_BG),
    backgroundFilter: safeStyle(g.backgroundFilter, 'brightness(1)'),
    gutter: safeNum(g.gutter, 16),
    lang: safeStr(g.lang, 'zh-cn'),
    globalFontFamily: safeFont(g.globalFontFamily),
    siteTitle: safeStr(g.siteTitle, '平行线工作台'),
    disabledDialogAnimation: safeBool(g.disabledDialogAnimation, false),
    showMenuBtn: safeBool(g.showMenuBtn, true),
    css: '',
    js: '',
    siteIcon: '',
    loadHarmonyOSFont: false,
  }
}

function sanitizeSyncLayout(raw: any): Record<string, any> {
  return {
    list: Array.isArray(raw?.list) ? raw.list.map(sanitizeSyncElement).filter(Boolean) : [],
    affix: Array.isArray(raw?.affix) ? raw.affix.map(sanitizeSyncElement).filter(Boolean) : [],
    global: sanitizeSyncGlobal(raw?.global),
    showBackgroundEffect: safeBool(raw?.showBackgroundEffect, false),
    showRefreshBtn: safeBool(raw?.showRefreshBtn, false),
    backgroundEffectActive: safeNum(raw?.backgroundEffectActive, 0),
  }
}

/** 从 Pinia store 提取严格符合后端 v1 schema 的云同步快照 */
export function buildCloudSyncConfig(store: any): Record<string, any> {
  const tabList = Array.isArray(store.tabList)
    ? store.tabList
        .filter((t: any) => t && typeof t === 'object' && typeof t.id === 'string' && t.id.trim())
        .map((t: any) => ({
          id: t.id.trim(),
          name: safeStr(t.name),
          selected: safeBool(t.selected, false),
          data: t.data ? sanitizeSyncLayout(t.data) : null,
        }))
    : []

  return {
    ...sanitizeSyncLayout(store),
    tabList,
    showTabSwitchBtn:
      typeof store.showTabSwitchBtn === 'number' || typeof store.showTabSwitchBtn === 'boolean'
        ? store.showTabSwitchBtn
        : true,
    enableKeydownSwitchTab: safeBool(store.enableKeydownSwitchTab, true),
  }
}

/** 将云端快照应用到本地 store，同时按组件 ID 保留本地私密数据（待办/笔记/天气城市/闹钟） */
export function applyCloudConfigToStore(store: any, cloudConfig: Record<string, any>) {
  const localById = new Map<string, any>()
  for (const item of [...(store.list || []), ...(store.affix || [])]) {
    if (item?.i) localById.set(item.i, item)
  }

  const mergeLocalPrivate = (items: any[]) =>
    (items || []).map((item) => {
      const prev = localById.get(item.i)
      if (!prev || prev.material !== item.material) return item
      const next = JSON.parse(JSON.stringify(item))
      if (item.material === 'TodoList' && prev.componentSetting?.todo) {
        next.componentSetting.todo = prev.componentSetting.todo
      } else if (item.material === 'Editor' && prev.componentSetting?.markdown) {
        next.componentSetting.markdown = prev.componentSetting.markdown
      } else if (item.material === 'WeatherCard' && prev.componentSetting) {
        next.componentSetting = { ...prev.componentSetting }
      } else if (item.material === 'AlarmTimer' && prev.componentSetting) {
        next.componentSetting = {
          ...prev.componentSetting,
          ...(next.componentSetting || {}),
        }
      }
      return next
    })

  store.updateStates([
    { key: 'tabList', value: cloudConfig.tabList || [] },
    { key: 'list', value: mergeLocalPrivate(cloudConfig.list || []) },
    { key: 'affix', value: mergeLocalPrivate(cloudConfig.affix || []) },
    { key: 'showBackgroundEffect', value: Boolean(cloudConfig.showBackgroundEffect) },
    { key: 'showRefreshBtn', value: Boolean(cloudConfig.showRefreshBtn) },
    { key: 'showTabSwitchBtn', value: cloudConfig.showTabSwitchBtn ?? true },
    { key: 'enableKeydownSwitchTab', value: cloudConfig.enableKeydownSwitchTab !== false },
    { key: 'backgroundEffectActive', value: Number(cloudConfig.backgroundEffectActive) || 0 },
  ])
  if (cloudConfig.global) {
    store.updateGlobal(cloudConfig.global)
  }
}

function getMainAccessToken(): string | null {
  try {
    return (
      window.localStorage.getItem('parallellines.access_token') ||
      window.localStorage.getItem('access_token')
    )
  } catch {
    return null
  }
}

function getApiBase(): string {
  const envBase = (import.meta as any).env?.VITE_API_BASE_URL
  if (typeof envBase === 'string' && envBase.trim()) {
    return envBase.replace(/\/$/, '')
  }
  return '/api/v1'
}

export const cloudSyncState = reactive({
  status: 'guest' as CloudSyncStatus,
  userId: null as string | null,
  username: '' as string,
  revision: '0' as string,
  conflictRevision: '' as string,
  updatedAt: null as string | null,
  message: '' as string,
  applyingRemote: false,
})

let activeController: AbortController | null = null
let debounceTimer: number | undefined

function abortActive() {
  if (activeController) {
    activeController.abort()
    activeController = null
  }
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = getMainAccessToken()
  if (!token) throw new Error('NO_TOKEN')
  abortActive()
  activeController = new AbortController()
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    ...(init.headers as Record<string, string> | undefined),
  }
  return fetch(`${getApiBase()}${path}`, {
    ...init,
    headers,
    cache: 'no-store',
    signal: activeController.signal,
  })
}

export async function initCloudSync(store: any): Promise<void> {
  const token = getMainAccessToken()
  if (!token) {
    cloudSyncState.status = 'guest'
    cloudSyncState.userId = null
    cloudSyncState.username = ''
    cloudSyncState.revision = '0'
    cloudSyncState.message = '未登录主站，当前仅保存在本地浏览器'
    return
  }

  cloudSyncState.status = 'checking'
  cloudSyncState.message = '正在检查主站云配置...'

  try {
    const meRes = await apiFetch('/auth/me')
    if (meRes.status === 401) {
      cloudSyncState.status = 'guest'
      cloudSyncState.userId = null
      cloudSyncState.message = '登录已过期，当前使用本地模式'
      return
    }
    if (!meRes.ok) {
      cloudSyncState.status = 'offline'
      cloudSyncState.message = '暂时无法连接主站，已保留本地配置'
      return
    }
    const meJson = await meRes.json()
    const user = meJson?.data || meJson
    cloudSyncState.userId = String(user?.id || '')
    cloudSyncState.username = String(user?.nickname || user?.username || '')

    const cfgRes = await apiFetch('/workspace/config')
    if (cfgRes.status === 401) {
      cloudSyncState.status = 'guest'
      cloudSyncState.message = '会话未验证，当前使用本地模式'
      return
    }
    if (!cfgRes.ok) {
      cloudSyncState.status = 'offline'
      cloudSyncState.message = '暂时无法读取云配置，已保留本地配置'
      return
    }
    const cfgJson = await cfgRes.json()
    const snapshot: WorkspaceSnapshot = cfgJson?.data

    cloudSyncState.revision = snapshot?.revision || '0'
    cloudSyncState.updatedAt = snapshot?.updated_at || null

    if (cloudSyncState.revision === '0' || !snapshot?.config) {
      cloudSyncState.status = 'needs_first_upload'
      cloudSyncState.message = '该账号尚无云端工作台配置，可确认后首次上传'
      return
    }

    cloudSyncState.applyingRemote = true
    try {
      applyCloudConfigToStore(store, snapshot.config)
    } finally {
      cloudSyncState.applyingRemote = false
    }
    cloudSyncState.status = 'synced'
    cloudSyncState.message = `已与云端同步（v${cloudSyncState.revision}）`
  } catch (err: any) {
    if (err?.name === 'AbortError') return
    cloudSyncState.status = 'offline'
    cloudSyncState.message = '无法连接主站服务，当前修改保留在本地'
  }
}

export async function pushCloudConfig(store: any, overrideExpectedRevision?: string): Promise<boolean> {
  if (!getMainAccessToken()) {
    cloudSyncState.status = 'guest'
    cloudSyncState.message = '未登录主站，当前仅保存在本地浏览器'
    return false
  }

  const config = buildCloudSyncConfig(store)
  const serialized = JSON.stringify(config)
  const bytes = new TextEncoder().encode(serialized).length
  if (bytes > MAX_SYNC_CONFIG_BYTES) {
    cloudSyncState.status = 'too_large'
    cloudSyncState.message = `当前配置 ${(bytes / 1024).toFixed(1)} KiB，超过 128 KiB 云同步上限，已保留在本地`
    return false
  }

  const expectedRevision = overrideExpectedRevision ?? cloudSyncState.revision
  cloudSyncState.status = 'saving'
  cloudSyncState.message = '正在同步到云端...'

  try {
    const res = await apiFetch('/workspace/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        expected_revision: expectedRevision,
        schema_version: WORKSPACE_SCHEMA_VERSION,
        config,
      }),
    })

    if (res.status === 200 || res.status === 201) {
      const json = await res.json()
      const snapshot: WorkspaceSnapshot = json?.data
      cloudSyncState.revision = snapshot?.revision || expectedRevision
      cloudSyncState.updatedAt = snapshot?.updated_at || null
      cloudSyncState.conflictRevision = ''
      cloudSyncState.status = 'synced'
      cloudSyncState.message = `已云同步（v${cloudSyncState.revision}）`
      return true
    }

    if (res.status === 409) {
      const errJson = await res.json().catch(() => ({}))
      cloudSyncState.conflictRevision = String(errJson?.error?.details?.current_revision || '')
      cloudSyncState.status = 'conflict'
      cloudSyncState.message = '云端配置已在其他设备更新，当前本地修改已保留'
      return false
    }

    if (res.status === 413) {
      cloudSyncState.status = 'too_large'
      cloudSyncState.message = '云配置超过 128 KiB 上限，原配置已保留在本地'
      return false
    }

    if (res.status === 401) {
      cloudSyncState.status = 'guest'
      cloudSyncState.message = '登录已过期，当前修改已保留在本地'
      return false
    }

    const errJson = await res.json().catch(() => ({}))
    cloudSyncState.status = 'error'
    cloudSyncState.message = errJson?.error?.message || '同步失败，本地草稿已保留'
    return false
  } catch (err: any) {
    if (err?.name === 'AbortError') return false
    cloudSyncState.status = 'offline'
    cloudSyncState.message = '网络不可用，本地修改未丢失'
    return false
  }
}

export async function pullLatestCloudConfig(store: any): Promise<boolean> {
  try {
    const res = await apiFetch('/workspace/config')
    if (!res.ok) return false
    const json = await res.json()
    const snapshot: WorkspaceSnapshot = json?.data
    if (!snapshot) return false
    cloudSyncState.revision = snapshot.revision || '0'
    cloudSyncState.updatedAt = snapshot.updated_at || null
    cloudSyncState.conflictRevision = ''
    if (snapshot.config) {
      cloudSyncState.applyingRemote = true
      try {
        applyCloudConfigToStore(store, snapshot.config)
      } finally {
        cloudSyncState.applyingRemote = false
      }
      cloudSyncState.status = 'synced'
      cloudSyncState.message = `已采用云端最新版本（v${cloudSyncState.revision}）`
    } else {
      cloudSyncState.status = 'needs_first_upload'
    }
    return true
  } catch {
    cloudSyncState.status = 'offline'
    cloudSyncState.message = '拉取云端配置失败，请稍后重试'
    return false
  }
}

export function scheduleCloudSync(store: any) {
  if (cloudSyncState.applyingRemote) return
  if (cloudSyncState.status !== 'synced' && cloudSyncState.status !== 'dirty') return
  if (cloudSyncState.revision === '0') return

  cloudSyncState.status = 'dirty'
  cloudSyncState.message = '本地已修改，待同步...'
  if (debounceTimer) window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    pushCloudConfig(store)
  }, 1800)
}
