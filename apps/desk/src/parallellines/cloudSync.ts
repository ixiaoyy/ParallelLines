import { reactive } from 'vue'
import { isAllowedMaterial, isSafeHttpOrRelativeUrl } from './security'

export const WORKSPACE_SCHEMA_VERSION = 1
export const MAX_SYNC_CONFIG_BYTES = 128 * 1024

export type CloudSyncStatus =
  | 'guest'
  | 'account_changed'
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

const SESSION_KEYS = ['parallellines.access_token', 'access_token']
const LAYOUT_OWNER_KEY = 'pl_desk_cloud_layout_owner'
const DRAFT_REVISION_KEY = 'pl_desk_cloud_draft_revision'

function getMainAccessToken(): string | null {
  try {
    return window.localStorage.getItem(SESSION_KEYS[0]) || window.localStorage.getItem(SESSION_KEYS[1])
  } catch {
    return null
  }
}

function getApiBase(): string {
  return (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
}

export const cloudSyncState = reactive({
  status: 'guest' as CloudSyncStatus,
  userId: null as string | null,
  username: '',
  revision: '0',
  conflictRevision: '',
  updatedAt: null as string | null,
  message: '',
})

let activeController: AbortController | null = null
let debounceTimer: number | undefined
let verifiedToken: string | null = null
// Pinia 布局在同一浏览器资料内共享。已绑定的布局不因退出、刷新或换号而改归属。
let layoutOwner: string | null = null
let heldState: { status: CloudSyncStatus; message: string; autoSave: boolean } | null = null
let syncedLayout: string | undefined

function setStatus(status: CloudSyncStatus, message: string) {
  cloudSyncState.status = status
  cloudSyncState.message = message
}

function cancelPending() {
  window.clearTimeout(debounceTimer)
  debounceTimer = undefined
  activeController?.abort()
  activeController = null
}

function suspendSession() {
  if (verifiedToken) {
    const { status, message } = cloudSyncState
    heldState = { status, message, autoSave: debounceTimer !== undefined }
    if (status === 'saving') {
      heldState = { status: 'dirty', message: '上次保存结果待确认，本地布局已保留', autoSave: false }
    } else if (status === 'checking') {
      heldState = { status: 'offline', message: '读取已中断，本地布局已保留', autoSave: false }
    }
  }
  cancelPending()
  verifiedToken = null
  cloudSyncState.userId = null
  cloudSyncState.username = ''
}

function layoutBelongsTo(userId: string): boolean {
  const persistedOwner = window.localStorage.getItem(LAYOUT_OWNER_KEY)
  return (!layoutOwner || layoutOwner === userId) && (!persistedOwner || persistedOwner === userId)
}

function showAccountChanged() {
  setStatus('account_changed', '此浏览器的布局已绑定另一账号。请换回原账号，或用独立浏览器资料同步当前账号。')
}

/** 整次操作只使用已捕获的 token；换号或卸载后不发送后续请求，也不消费旧响应。 */
async function runCloudRequest(
  store: any,
  token: string,
  action: (request: (path: string, init?: RequestInit) => Promise<Response>, current: () => boolean) => Promise<boolean>,
): Promise<boolean> {
  const controller = new AbortController()
  activeController = controller
  const timer = window.setTimeout(() => controller.abort(), 10_000)
  const sameSession = () => activeController === controller && getMainAccessToken() === token
  const current = () => sameSession() && !controller.signal.aborted
  try {
    return await action((path, init) => {
      if (!current()) throw new DOMException('Cloud session changed', 'AbortError')
      return fetch(getApiBase() + path, {
        ...init,
        headers: { ...init?.headers, Authorization: 'Bearer ' + token },
        cache: 'no-store',
        signal: controller.signal,
      })
    }, current)
  } catch {
    if (sameSession()) setStatus('offline', '云同步暂时不可用，当前布局已保留')
    return false
  } finally {
    window.clearTimeout(timer)
    if (activeController === controller) {
      activeController = null
      if (getMainAccessToken() !== token) void initCloudSync(store)
    }
  }
}

function requestRejected(response: Response): boolean {
  if (response.ok) return false
  if (response.status === 401) {
    suspendSession()
    setStatus('guest', '登录已过期，当前布局已保留')
  } else {
    setStatus('error', '云端请求失败，当前布局已保留')
  }
  return true
}

function applySnapshot(store: any, snapshot: WorkspaceSnapshot) {
  // 保持 checking 状态直到布局写完，避免把服务器下发的修改当成本地编辑上传。
  setStatus('checking', '正在载入云端配置…')
  if (snapshot.config) applyCloudConfigToStore(store, snapshot.config)
  syncedLayout = snapshot.config ? JSON.stringify(buildCloudSyncConfig(store)) : undefined
  window.localStorage.removeItem(DRAFT_REVISION_KEY)
  cloudSyncState.revision = snapshot.revision
  cloudSyncState.updatedAt = snapshot.updated_at
  cloudSyncState.conflictRevision = ''
  if (snapshot.revision === '0' || !snapshot.config) {
    setStatus('needs_first_upload', '该账号尚无云端工作台配置，可确认后首次上传')
  } else {
    setStatus('synced', '已与云端同步（v' + snapshot.revision + '）')
  }
}

function restoreSnapshot(store: any, snapshot: WorkspaceSnapshot) {
  // 草稿本体仍由 Pinia 保存，只记录它基于哪个云端版本；换号期间刷新也不能覆盖草稿。
  const draftRevision = window.localStorage.getItem(DRAFT_REVISION_KEY)
  if (!snapshot.config || !draftRevision) {
    applySnapshot(store, snapshot)
    return
  }
  cloudSyncState.revision = draftRevision
  cloudSyncState.updatedAt = snapshot.updated_at
  if (draftRevision === snapshot.revision) {
    setStatus('dirty', '本地草稿已保留，可继续同步')
  } else {
    cloudSyncState.conflictRevision = snapshot.revision
    setStatus('conflict', '云端版本已更新，当前本地草稿已保留')
  }
}

/** 核实当前主站账号后才恢复同步；同账号续发凭据时保留本地草稿与原版本。 */
export async function initCloudSync(store: any): Promise<void> {
  suspendSession()
  const token = getMainAccessToken()
  if (!token) {
    setStatus('guest', '未登录主站，当前仅保存在本地浏览器')
    return
  }
  setStatus('checking', '正在检查主站云配置…')
  await runCloudRequest(store, token, async (request, current) => {
    const me = await request('/auth/me')
    if (!current() || requestRejected(me)) return false
    const { data: user } = await me.json()
    if (!current()) return false
    if (!user || typeof user.id !== 'string' || !user.id) {
      setStatus('error', '无法确认当前账号，已暂停云同步')
      return false
    }
    if (!layoutBelongsTo(user.id)) {
      showAccountChanged()
      return false
    }
    // 先建立本地归属，再允许加载或提交布局；不修改已有本地布局与私密物料。
    window.localStorage.setItem(LAYOUT_OWNER_KEY, user.id)
    layoutOwner = user.id
    const resume = heldState
    if (resume) {
      setStatus(resume.status, resume.message)
      heldState = null
    } else {
      const response = await request('/workspace/config')
      if (!current() || requestRejected(response)) return false
      const { data } = await response.json()
      if (!current()) return false
      if (!layoutBelongsTo(user.id)) {
        showAccountChanged()
        return false
      }
      restoreSnapshot(store, data)
    }
    verifiedToken = token
    cloudSyncState.userId = user.id
    cloudSyncState.username = user.nickname || user.username
    if (resume?.autoSave) scheduleCloudSync(store)
    return true
  })
}

function checkedToken(store: any): string | null {
  if (activeController || !verifiedToken || !cloudSyncState.userId) return null
  if (getMainAccessToken() !== verifiedToken) {
    void initCloudSync(store)
    return null
  }
  try {
    if (layoutBelongsTo(cloudSyncState.userId)) return verifiedToken
    suspendSession()
    showAccountChanged()
  } catch {
    setStatus('error', '无法确认本地布局归属，已暂停云同步')
  }
  return null
}

/** 只提交已核实账号的快照；首次写入和冲突后覆盖仍由用户显式确认。 */
export async function pushCloudConfig(store: any, overrideExpectedRevision?: string): Promise<boolean> {
  const token = checkedToken(store)
  if (!token) return false
  const expectedRevision = overrideExpectedRevision ?? cloudSyncState.revision
  if (cloudSyncState.status === 'needs_first_upload' && overrideExpectedRevision !== '0') return false
  if (cloudSyncState.status === 'conflict' && overrideExpectedRevision !== cloudSyncState.conflictRevision) return false
  window.clearTimeout(debounceTimer)
  debounceTimer = undefined
  const config = buildCloudSyncConfig(store)
  const serialized = JSON.stringify(config)
  const bytes = new TextEncoder().encode(serialized).length
  if (bytes > MAX_SYNC_CONFIG_BYTES) {
    setStatus('too_large', '当前配置超过 128 KiB 云同步上限，已保留在本地')
    return false
  }
  setStatus('saving', '正在同步到云端…')
  return runCloudRequest(store, token, async (request, current) => {
    window.localStorage.setItem(DRAFT_REVISION_KEY, cloudSyncState.revision)
    const response = await request('/workspace/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ expected_revision: expectedRevision, schema_version: WORKSPACE_SCHEMA_VERSION, config }),
    })
    if (!current()) return false
    if (response.status === 401) {
      requestRejected(response)
      return false
    }
    const json = await response.json()
    if (!current()) return false
    if (response.ok) {
      syncedLayout = serialized
      cloudSyncState.revision = json.data.revision
      cloudSyncState.updatedAt = json.data.updated_at
      cloudSyncState.conflictRevision = ''
      setStatus('synced', '已云同步（v' + cloudSyncState.revision + '）')
      // 保存期间仍可编辑；只为后来产生的新布局安排下一次保存。
      if (serialized !== JSON.stringify(buildCloudSyncConfig(store))) {
        scheduleCloudSync(store)
      } else {
        window.localStorage.removeItem(DRAFT_REVISION_KEY)
      }
      return true
    }
    if (response.status === 409) {
      cloudSyncState.conflictRevision = String(json?.error?.details?.current_revision || '')
      setStatus('conflict', '云端配置已在其他设备更新，当前本地修改已保留')
    } else if (response.status === 413) {
      setStatus('too_large', '云配置超过 128 KiB 上限，原配置已保留在本地')
    } else {
      setStatus('error', json?.error?.message || '同步失败，本地草稿已保留')
    }
    return false
  })
}

/** 用户主动采用云端版本；本地防抖保存必须先取消，不能覆盖选中的版本。 */
export async function pullLatestCloudConfig(store: any): Promise<boolean> {
  const token = checkedToken(store)
  if (!token) return false
  cancelPending()
  setStatus('checking', '正在读取云端配置…')
  return runCloudRequest(store, token, async (request, current) => {
    const response = await request('/workspace/config')
    if (!current() || requestRejected(response)) return false
    const { data } = await response.json()
    if (!current()) return false
    if (!cloudSyncState.userId || !layoutBelongsTo(cloudSyncState.userId)) {
      suspendSession()
      showAccountChanged()
      return false
    }
    applySnapshot(store, data)
    return true
  })
}

function scheduleCloudSync(store: any) {
  if (cloudSyncState.status !== 'synced' && cloudSyncState.status !== 'dirty') return
  if (cloudSyncState.revision === '0') return
  // 组件挂载、开关对话框等只影响本地状态，不应消耗一个云端版本。
  if (cloudSyncState.status === 'synced' && syncedLayout === JSON.stringify(buildCloudSyncConfig(store))) return

  try {
    if (window.localStorage.getItem(DRAFT_REVISION_KEY) !== cloudSyncState.revision) {
      window.localStorage.setItem(DRAFT_REVISION_KEY, cloudSyncState.revision)
    }
  } catch {
    setStatus('error', '无法记录本地草稿版本，已暂停自动同步')
    return
  }
  setStatus('dirty', '本地已修改，待同步…')
  window.clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(() => {
    debounceTimer = undefined
    // 初始化时可能连续调整再恢复同一个值，以真正发送时的投影为准。
    if (syncedLayout === JSON.stringify(buildCloudSyncConfig(store))) {
      if (checkedToken(store)) {
        window.localStorage.removeItem(DRAFT_REVISION_KEY)
        setStatus('synced', '已与云端同步（v' + cloudSyncState.revision + '）')
      }
      return
    }
    void pushCloudConfig(store)
  }, 1800)
}

/** 在工作台挂载期间跟随主站登录态，销毁时取消计时和请求。 */
export function startCloudSync(store: any): () => void {
  const onStorage = (event: StorageEvent) => {
    if (event.storageArea === window.localStorage
      && (event.key === null || SESSION_KEYS.includes(event.key) || event.key === LAYOUT_OWNER_KEY)
      && (getMainAccessToken() !== verifiedToken || event.key === LAYOUT_OWNER_KEY)) {
      void initCloudSync(store)
    }
  }
  window.addEventListener('storage', onStorage)
  const unsubscribe = store.$subscribe(() => scheduleCloudSync(store), { flush: 'sync' })
  void initCloudSync(store)
  return () => {
    window.removeEventListener('storage', onStorage)
    unsubscribe()
    suspendSession()
  }
}
