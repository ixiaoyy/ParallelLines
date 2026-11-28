<template>
  <div
    class="hot-board-card"
    :style="{
      padding: (componentSetting.padding ?? 16) + 'px',
      color: componentSetting.textColor || '#f8fafc',
      fontFamily: componentSetting.fontFamily || undefined,
    }"
  >
    <div class="hot-board-header">
      <div class="hot-tabs" role="tablist" aria-label="热榜来源">
        <button
          v-for="tab in SOURCES"
          :key="tab.id"
          type="button"
          role="tab"
          class="hot-tab"
          :class="{ active: activeSource === tab.id }"
          :aria-selected="activeSource === tab.id"
          @click="switchSource(tab.id)"
        >
          <span class="hot-tab-dot" :style="{ background: tab.color }" />
          <span>{{ tab.shortLabel }}</span>
        </button>
      </div>
      <div class="hot-actions">
        <span v-if="updatedLabel" class="hot-updated" :class="{ stale: isStale }">
          {{ updatedLabel }}
        </span>
        <button
          type="button"
          class="hot-icon-btn"
          :class="{ spinning: loading }"
          :disabled="loading"
          title="刷新当前榜单"
          aria-label="刷新当前榜单"
          @click="loadHotList(true)"
        >
          ↻
        </button>
        <a
          class="hot-icon-btn"
          :href="currentSiteUrl"
          target="_blank"
          rel="noopener noreferrer"
          :title="`打开${currentSourceMeta.label}原站`"
          aria-label="打开原站"
        >
          ↗
        </a>
      </div>
    </div>

    <div v-if="loading && !items.length" class="hot-skeleton-list">
      <div v-for="n in Math.min(maxItems, 6)" :key="n" class="hot-skeleton-row">
        <span class="sk-rank" />
        <span class="sk-title" />
        <span class="sk-score" />
      </div>
    </div>

    <div v-else-if="errorMsg && !items.length" class="hot-error">
      <p class="hot-error-text">{{ errorMsg }}</p>
      <div class="hot-error-actions">
        <button type="button" class="hot-retry-btn" @click="loadHotList(true)">重试</button>
        <a
          class="hot-site-link"
          :href="currentSiteUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          前往{{ currentSourceMeta.label }} ↗
        </a>
      </div>
    </div>

    <ol v-else class="hot-list">
      <li v-for="item in visibleItems" :key="`${activeSource}-${item.rank}-${item.title}`" class="hot-row">
        <a
          class="hot-link"
          :href="item.url"
          target="_blank"
          rel="noopener noreferrer"
          :title="item.title"
        >
          <span
            v-if="showRankBadge"
            class="hot-rank"
            :class="`rank-${item.rank <= 3 ? item.rank : 'other'}`"
          >
            {{ item.rank }}
          </span>
          <span class="hot-title">{{ item.title }}</span>
          <span v-if="item.tag" class="hot-tag" :class="tagTone(item.tag)">{{ item.tag }}</span>
          <span v-if="item.hot_value" class="hot-score">{{ item.hot_value }}</span>
        </a>
      </li>
    </ol>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, onMounted, onUnmounted, ref, watch } from 'vue'

type HotSourceId = 'weibo' | 'baidu' | 'bilibili' | 'hackernews'

interface HotListItem {
  rank: number
  title: string
  url: string
  hot_value: string
  tag: string
}

interface HotListSnapshot {
  source: string
  label: string
  site_url: string
  updated_at: string
  stale: boolean
  items: HotListItem[]
}

const SOURCES: Array<{ id: HotSourceId; label: string; shortLabel: string; color: string; siteUrl: string }> = [
  { id: 'weibo', label: '微博热搜', shortLabel: '微博', color: '#e6162d', siteUrl: 'https://s.weibo.com/top/summary' },
  { id: 'baidu', label: '百度热搜', shortLabel: '百度', color: '#2932e1', siteUrl: 'https://top.baidu.com/board?tab=realtime' },
  { id: 'bilibili', label: 'B站热门', shortLabel: 'B站', color: '#fb7299', siteUrl: 'https://www.bilibili.com/v/popular/all' },
  { id: 'hackernews', label: 'Hacker News', shortLabel: 'HN', color: '#ff6600', siteUrl: 'https://news.ycombinator.com/' },
]

const VALID_SOURCES = new Set<HotSourceId>(['weibo', 'baidu', 'bilibili', 'hackernews'])
const AUTO_REFRESH_MS = 5 * 60 * 1000

export default defineComponent({
  name: 'HotBoard',
  props: {
    componentSetting: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    const resolveDefaultSource = (): HotSourceId => {
      const raw = String(props.componentSetting?.defaultSource || 'weibo') as HotSourceId
      return VALID_SOURCES.has(raw) ? raw : 'weibo'
    }

    const activeSource = ref<HotSourceId>(resolveDefaultSource())
    const items = ref<HotListItem[]>([])
    const siteUrl = ref('')
    const updatedAt = ref<string | null>(null)
    const isStale = ref(false)
    const loading = ref(false)
    const errorMsg = ref('')
    const nowTick = ref(Date.now())

    let controller: AbortController | null = null
    let refreshTimer: number | null = null
    let clockTimer: number | null = null

    const maxItems = computed(() => {
      const raw = Number(props.componentSetting?.maxItems ?? 10)
      if (!Number.isFinite(raw)) return 10
      return Math.min(20, Math.max(3, Math.round(raw)))
    })

    const showRankBadge = computed(() => props.componentSetting?.showRankBadge !== false)

    const currentSourceMeta = computed(
      () => SOURCES.find((s) => s.id === activeSource.value) || SOURCES[0],
    )

    const currentSiteUrl = computed(() => siteUrl.value || currentSourceMeta.value.siteUrl)

    const visibleItems = computed(() => items.value.slice(0, maxItems.value))

    const updatedLabel = computed(() => {
      if (!updatedAt.value) return ''
      const ts = Date.parse(updatedAt.value)
      if (!Number.isFinite(ts)) return ''
      const diffMin = Math.max(0, Math.floor((nowTick.value - ts) / 60_000))
      const base = diffMin < 1 ? '刚刚' : `${diffMin}分钟前`
      return isStale.value ? `${base} · 缓存` : base
    })

    const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

    const loadHotList = async (force = false) => {
      if (controller) controller.abort()
      controller = new AbortController()
      loading.value = true
      errorMsg.value = ''

      try {
        const params = new URLSearchParams({ source: activeSource.value })
        if (force) params.set('refresh', 'true')
        const res = await fetch(`${apiBase}/workspace/hot-lists?${params.toString()}`, {
          signal: controller.signal,
          headers: { Accept: 'application/json' },
        })
        const json = await res.json().catch(() => null)
        if (!res.ok || !json?.data) {
          throw new Error(json?.error?.message || `暂时无法获取${currentSourceMeta.value.label}`)
        }
        const data = json.data as HotListSnapshot
        items.value = Array.isArray(data.items) ? data.items : []
        siteUrl.value = data.site_url || currentSourceMeta.value.siteUrl
        updatedAt.value = data.updated_at || new Date().toISOString()
        isStale.value = Boolean(data.stale)
      } catch (err: any) {
        if (err?.name === 'AbortError') return
        errorMsg.value = err?.message || `暂时无法获取${currentSourceMeta.value.label}`
      } finally {
        loading.value = false
      }
    }

    const switchSource = (source: HotSourceId) => {
      if (activeSource.value === source) return
      activeSource.value = source
      items.value = []
      updatedAt.value = null
      isStale.value = false
      loadHotList(false)
    }

    const tagTone = (tag: string) => {
      if (tag.includes('爆') || tag.includes('沸')) return 'tone-hot'
      if (tag.includes('热')) return 'tone-warm'
      if (tag.includes('新')) return 'tone-new'
      return 'tone-neutral'
    }

    watch(
      () => props.componentSetting?.defaultSource,
      (next) => {
        if (typeof next === 'string' && VALID_SOURCES.has(next as HotSourceId)) {
          if (activeSource.value !== next) {
            switchSource(next as HotSourceId)
          }
        }
      },
    )

    onMounted(() => {
      loadHotList(false)
      refreshTimer = window.setInterval(() => loadHotList(false), AUTO_REFRESH_MS)
      clockTimer = window.setInterval(() => {
        nowTick.value = Date.now()
      }, 60_000)
    })

    onUnmounted(() => {
      if (controller) controller.abort()
      if (refreshTimer) window.clearInterval(refreshTimer)
      if (clockTimer) window.clearInterval(clockTimer)
    })

    return {
      SOURCES,
      activeSource,
      items,
      visibleItems,
      maxItems,
      showRankBadge,
      currentSourceMeta,
      currentSiteUrl,
      updatedLabel,
      isStale,
      loading,
      errorMsg,
      switchSource,
      loadHotList,
      tagTone,
    }
  },
})
</script>

<style scoped lang="scss">
.hot-board-card {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
  user-select: none;
}

.hot-board-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-shrink: 0;
}

.hot-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow-x: auto;
  scrollbar-width: none;
  &::-webkit-scrollbar {
    display: none;
  }
}

.hot-tab {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  opacity: 0.76;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.18s ease;

  &:hover {
    opacity: 0.96;
    background: rgba(255, 255, 255, 0.13);
  }

  &.active {
    opacity: 1;
    background: rgba(255, 255, 255, 0.2);
    border-color: rgba(255, 255, 255, 0.34);
    font-weight: 600;
  }
}

.hot-tab-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.hot-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.hot-updated {
  font-size: 11px;
  opacity: 0.62;
  white-space: nowrap;
  &.stale {
    color: #fcd34d;
    opacity: 0.9;
  }
}

.hot-icon-btn {
  width: 24px;
  height: 24px;
  border-radius: 7px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.08);
  color: inherit;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  text-decoration: none;
  transition: background 0.16s ease, transform 0.16s ease;

  &:hover:not(:disabled) {
    background: rgba(255, 255, 255, 0.18);
  }

  &:disabled {
    opacity: 0.5;
    cursor: default;
  }

  &.spinning {
    animation: hot-spin 0.8s linear infinite;
  }
}

@keyframes hot-spin {
  to {
    transform: rotate(360deg);
  }
}

.hot-list {
  list-style: none;
  margin: 0;
  padding: 0 2px 0 0;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.22) transparent;
}

.hot-row {
  min-width: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  &:last-child {
    border-bottom: none;
  }
}

.hot-link {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 7px 8px;
  border-radius: 10px;
  color: inherit;
  text-decoration: none;
  transition: background 0.15s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.09);
  }
}

.hot-rank {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &.rank-1 {
    background: linear-gradient(135deg, #ef4444, #f97316);
    color: #fff;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.35);
  }
  &.rank-2 {
    background: linear-gradient(135deg, #f97316, #fb923c);
    color: #fff;
  }
  &.rank-3 {
    background: linear-gradient(135deg, #f59e0b, #fbbf24);
    color: #fff;
  }
  &.rank-other {
    background: rgba(255, 255, 255, 0.08);
    opacity: 0.72;
  }
}

.hot-title {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  line-height: 1.35;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hot-tag {
  font-size: 10px;
  line-height: 1;
  padding: 3px 5px;
  border-radius: 4px;
  font-weight: 600;
  flex-shrink: 0;

  &.tone-hot {
    background: rgba(239, 68, 68, 0.28);
    color: #fecaca;
  }
  &.tone-warm {
    background: rgba(249, 115, 22, 0.28);
    color: #fed7aa;
  }
  &.tone-new {
    background: rgba(56, 189, 248, 0.25);
    color: #bae6fd;
  }
  &.tone-neutral {
    background: rgba(255, 255, 255, 0.14);
    color: inherit;
  }
}

.hot-score {
  font-size: 11px;
  opacity: 0.56;
  white-space: nowrap;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.hot-skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 2px;
}

.hot-skeleton-row {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 24px;
}

.sk-rank,
.sk-title,
.sk-score {
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.12);
  animation: hot-pulse 1.3s ease-in-out infinite;
}

.sk-rank {
  width: 19px;
  height: 19px;
  flex-shrink: 0;
}

.sk-title {
  flex: 1;
  height: 14px;
}

.sk-score {
  width: 44px;
  height: 12px;
  flex-shrink: 0;
}

@keyframes hot-pulse {
  0%,
  100% {
    opacity: 0.45;
  }
  50% {
    opacity: 0.85;
  }
}

.hot-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  text-align: center;
  padding: 12px;
}

.hot-error-text {
  margin: 0;
  font-size: 13px;
  opacity: 0.82;
}

.hot-error-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hot-retry-btn,
.hot-site-link {
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 12px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.12);
  color: inherit;
  cursor: pointer;
  text-decoration: none;
  &:hover {
    background: rgba(255, 255, 255, 0.22);
  }
}
</style>
