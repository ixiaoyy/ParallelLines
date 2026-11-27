/**
 * ParallelLines Desk 同源安全与物料白名单校验模块。
 * 在本地读取、JSON 导入、剪贴板粘贴与布局渲染四处统一生效。
 */

export const ALLOWED_MATERIALS = new Set<string>([
  'Empty',
  'Clock',
  'Day',
  'Search',
  'AiSearch',
  'Bookmark',
  'Collection',
  'TodoList',
  'Editor',
  'CountDown',
  'SlackCountdown',
  'WeatherCard',
  'AlarmTimer',
])

export function isAllowedMaterial(material: unknown): material is string {
  return typeof material === 'string' && ALLOWED_MATERIALS.has(material)
}

export function isSafeHttpOrRelativeUrl(url: unknown): boolean {
  if (typeof url !== 'string') return false
  const trimmed = url.trim()
  if (!trimmed) return true
  if (trimmed.startsWith('/')) return !trimmed.startsWith('//')
  try {
    const parsed = new URL(trimmed)
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
  } catch {
    return false
  }
}

export function sanitizeGlobal(raw: any): any {
  const src = raw && typeof raw === 'object' ? { ...raw } : {}
  // 彻底禁用全局自定义 CSS/JS 注入与外部远程字体/随机图代理
  src.css = ''
  src.js = ''
  src.loadHarmonyOSFont = false

  if (typeof src.background === 'string') {
    if (
      src.background.includes('api/randomPhoto') ||
      src.background.includes('cdn.kongfandong.cn') ||
      /javascript:/i.test(src.background)
    ) {
      src.background = 'linear-gradient(135deg, #1b2838 0%, #2b4162 48%, #3c6e71 100%)'
    }
  }

  if (typeof src.siteIcon === 'string' && src.siteIcon.trim()) {
    const icon = src.siteIcon.trim()
    const isSafeDataImg = /^data:image\/(png|jpeg|webp|x-icon);base64,/i.test(icon)
    if (!isSafeDataImg && !isSafeHttpOrRelativeUrl(icon)) {
      src.siteIcon = ''
    }
  }

  return src
}

function sanitizeBookmarkList(items: any): any[] {
  if (!Array.isArray(items)) return []
  return items
    .filter((entry) => entry && typeof entry === 'object')
    .map((entry) => {
      const next = { ...entry }
      if (typeof next.url === 'string' && !isSafeHttpOrRelativeUrl(next.url)) {
        next.url = ''
      }
      if (typeof next.iconPath === 'string' && next.iconPath.includes('cdn.kongfandong.cn')) {
        next.iconPath = ''
      }
      if (Array.isArray(next.children)) {
        next.children = sanitizeBookmarkList(next.children)
      }
      return next
    })
}

export function sanitizeComponent(raw: any): any | null {
  if (!raw || typeof raw !== 'object') return null
  if (!isAllowedMaterial(raw.material)) return null

  const item = { ...raw }
  if (typeof item.background === 'string' && /javascript:|cdn\.kongfandong\.cn/i.test(item.background)) {
    item.background = 'rgba(255, 255, 255, 0.14)'
  }

  if (item.actionSetting && typeof item.actionSetting === 'object') {
    const action = { ...item.actionSetting }
    if (action.actionClickType === 1 && action.actionClickValue) {
      if (!isAllowedMaterial(action.actionClickValue.material)) {
        action.actionType = 0
        action.actionClickValue = {}
      }
    }
    if (action.actionClickType === 2 && action.actionClickValue) {
      if (!isSafeHttpOrRelativeUrl(action.actionClickValue.url)) {
        action.actionType = 0
        action.actionClickValue = {}
      }
    }
    item.actionSetting = action
  }

  if (item.componentSetting && typeof item.componentSetting === 'object') {
    const setting = { ...item.componentSetting }
    if (item.material === 'Bookmark' && Array.isArray(setting.bookmark)) {
      setting.bookmark = sanitizeBookmarkList(setting.bookmark)
      // 禁止通过书签内嵌任意第三方 iframe
      if (setting.jumpType === 3) {
        setting.jumpType = 1
      }
    }
    if (item.material === 'Search') {
      const cleanEngines = (list: any) =>
        Array.isArray(list)
          ? list
              .filter((e) => e && typeof e === 'object' && isSafeHttpOrRelativeUrl(e.link))
              .map((e) => ({
                ...e,
                iconPath:
                  typeof e.iconPath === 'string' && e.iconPath.includes('cdn.kongfandong.cn')
                    ? ''
                    : e.iconPath,
              }))
          : []
      if (Array.isArray(setting.engineList)) setting.engineList = cleanEngines(setting.engineList)
      if (Array.isArray(setting.backupEngineList)) {
        setting.backupEngineList = cleanEngines(setting.backupEngineList)
      }
    }
    item.componentSetting = setting
  }

  return item
}

export function sanitizeComponentList(list: unknown): { items: any[]; removedCount: number } {
  if (!Array.isArray(list)) return { items: [], removedCount: 0 }
  const items: any[] = []
  let removedCount = 0
  for (const entry of list) {
    const clean = sanitizeComponent(entry)
    if (clean) {
      items.push(clean)
    } else {
      removedCount += 1
    }
  }
  return { items, removedCount }
}

export function sanitizeDashboardPayload(raw: any): {
  payload: any
  removedCount: number
} {
  if (!raw || typeof raw !== 'object') {
    throw new Error('配置格式无效')
  }
  const cleanList = sanitizeComponentList(raw.list)
  const cleanAffix = sanitizeComponentList(raw.affix)
  let removedCount = cleanList.removedCount + cleanAffix.removedCount

  const cleanTabs = Array.isArray(raw.tabList)
    ? raw.tabList
        .filter((tab: any) => tab && typeof tab === 'object')
        .map((tab: any) => {
          if (!tab.data || typeof tab.data !== 'object') return { ...tab }
          const tabListClean = sanitizeComponentList(tab.data.list)
          const tabAffixClean = sanitizeComponentList(tab.data.affix)
          removedCount += tabListClean.removedCount + tabAffixClean.removedCount
          return {
            ...tab,
            data: {
              ...tab.data,
              list: tabListClean.items,
              affix: tabAffixClean.items,
              global: sanitizeGlobal(tab.data.global),
            },
          }
        })
    : []

  return {
    removedCount,
    payload: {
      list: cleanList.items,
      affix: cleanAffix.items,
      global: sanitizeGlobal(raw.global),
      showBackgroundEffect: Boolean(raw.showBackgroundEffect),
      showRefreshBtn: raw.showRefreshBtn !== false,
      tabList: cleanTabs,
      showTabSwitchBtn: raw.showTabSwitchBtn ?? true,
      enableKeydownSwitchTab: raw.enableKeydownSwitchTab !== false,
      backgroundEffectActive: Number(raw.backgroundEffectActive) || 0,
    },
  }
}
