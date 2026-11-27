import { ElNotification } from 'element-plus'
import { uid } from '@/utils'
import { isSafeHttpOrRelativeUrl } from './security'

export interface PinShortcutRequest {
  title: string
  url: string
  iconText: string
  bgColor: string
}

const SAFE_COLOR_RE = /^#[0-9a-fA-F]{3,8}$/

/**
 * 解析来自游戏站、工具站等子站的「固定到工作台」URL 参数：
 * ?pin_title=蛇蛇出洞&pin_url=https://pingxingxian.space/play/snake-escape&pin_icon=蛇&pin_color=%2310b981
 */
export function parsePinShortcutFromLocation(): PinShortcutRequest | null {
  const params = new URLSearchParams(window.location.search)
  const rawTitle = (params.get('pin_title') || '').trim()
  const rawUrl = (params.get('pin_url') || '').trim()
  if (!rawTitle || !rawUrl) return null
  if (!isSafeHttpOrRelativeUrl(rawUrl)) return null

  const rawIcon = (params.get('pin_icon') || '').trim()
  const rawColor = (params.get('pin_color') || '').trim()

  return {
    title: rawTitle.slice(0, 24),
    url: rawUrl.slice(0, 512),
    iconText: rawIcon.slice(0, 2) || rawTitle.slice(0, 1),
    bgColor: SAFE_COLOR_RE.test(rawColor) ? rawColor : '#2563eb',
  }
}

export function clearPinQueryFromLocation() {
  const url = new URL(window.location.href)
  url.searchParams.delete('pin_title')
  url.searchParams.delete('pin_url')
  url.searchParams.delete('pin_icon')
  url.searchParams.delete('pin_color')
  window.history.replaceState({}, '', url.pathname + url.search + url.hash)
}

export function handleIncomingPinShortcut(store: any) {
  const req = parsePinShortcutFromLocation()
  if (!req) return

  clearPinQueryFromLocation()

  const bookmarkComp = (store.list || []).find((item: any) => item?.material === 'Bookmark')
  if (!bookmarkComp) {
    ElNotification({
      title: '无法固定',
      type: 'warning',
      message: '当前工作台未添加书签导航组件，请先添加书签组件后再试',
    })
    return
  }

  const existingList: any[] = bookmarkComp.componentSetting?.bookmark || []
  if (existingList.some((b: any) => b?.url === req.url)) {
    ElNotification({
      title: '已在工作台',
      type: 'info',
      message: `「${req.title}」已经在你的工作台快捷入口中`,
    })
    return
  }

  if (!window.confirm(`是否将「${req.title}」添加到你的工作台快捷入口？\n链接：${req.url}`)) {
    return
  }

  const nextComp = JSON.parse(JSON.stringify(bookmarkComp))
  if (!Array.isArray(nextComp.componentSetting.bookmark)) {
    nextComp.componentSetting.bookmark = []
  }
  nextComp.componentSetting.bookmark.push({
    id: `pin-${uid()}`,
    title: req.title,
    url: req.url,
    iconType: 'text',
    iconText: req.iconText,
    bgColor: req.bgColor,
    iconPath: '#ffffff',
    type: 'icon',
  })
  store.editComponent(nextComp)

  ElNotification({
    title: '固定成功',
    type: 'success',
    message: `已将「${req.title}」添加到工作台快捷入口`,
  })
}
