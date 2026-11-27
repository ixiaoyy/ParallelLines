const badgeSvg = (title: string, accent: string) =>
  `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="256" height="140" viewBox="0 0 256 140"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="${accent}" stop-opacity="0.22"/><stop offset="100%" stop-color="#1e293b" stop-opacity="0.08"/></linearGradient></defs><rect width="256" height="140" rx="14" fill="url(#g)"/><rect x="1" y="1" width="254" height="138" rx="13" fill="none" stroke="${accent}" stroke-opacity="0.35"/><text x="128" y="76" text-anchor="middle" font-family="system-ui,-apple-system,sans-serif" font-size="20" font-weight="600" fill="#334155">${title}</text></svg>`
  )}`

export const MATERIAL_LIST_MAP: Record<string, MaterialConstanst> = {
  Clock: {
    label: 'Clock',
    text: '时钟',
    img: badgeSvg('时钟', '#3b82f6')
  },
  SlackCountdown: {
    label: 'SlackCountdown',
    text: '下班倒计时',
    img: badgeSvg('下班倒计时', '#10b981')
  },
  EventCountdown: {
    label: 'EventCountdown',
    text: '事件倒计时',
    img: badgeSvg('事件倒计时', '#38bdf8')
  },
  AiSearch: {
    label: 'AiSearch',
    text: 'AI 智能搜索',
    img: badgeSvg('AI 智能搜索', '#6366f1')
  },
  WeatherCard: {
    label: 'WeatherCard',
    text: '天气',
    img: badgeSvg('城市天气', '#38bdf8')
  },
  AlarmTimer: {
    label: 'AlarmTimer',
    text: '闹钟与定时',
    img: badgeSvg('闹钟与定时', '#a78bfa')
  },
  Search: {
    label: 'Search',
    text: '基础搜索栏',
    img: badgeSvg('基础搜索栏', '#64748b')
  },
  Bookmark: {
    label: 'Bookmark',
    text: '书签导航',
    img: badgeSvg('书签导航', '#0ea5e9')
  },
  TodoList: {
    label: 'TodoList',
    text: '备忘清单',
    img: badgeSvg('备忘清单', '#f59e0b')
  },
  Editor: {
    label: 'Editor',
    text: '随手便签',
    img: badgeSvg('随手便签', '#8b5cf6')
  },
  Day: {
    label: 'Day',
    text: '自定义日期',
    img: badgeSvg('自定义日期', '#14b8a6')
  },
  CountDown: {
    label: 'CountDown',
    text: '自定义倒计时',
    img: badgeSvg('自定义倒计时', '#ec4899')
  },
  Collection: {
    label: 'Collection',
    text: '导航收藏页',
    img: badgeSvg('导航收藏页', '#64748b')
  },
  Empty: {
    label: 'Empty',
    text: '占位区块',
    img: badgeSvg('占位区块', '#94a3b8')
  }
}

export const BG_IMG_TYPE_MAP = {
  Nature: '自然',
  People: '人物',
  Architecture: '建筑',
  Technology: '科技',
  Animals: '动物'
}

export const DAILY_HOT_CLASSIFY: Array<{ label: string; value: string }> = []
