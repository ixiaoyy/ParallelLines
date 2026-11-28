<template>
  <section
    class="weather-card"
    aria-label="城市天气"
    tabindex="0"
    :style="cardStyle"
  >
    <header class="weather-header">
      <div class="weather-place">
        <span class="weather-kicker">城市天气</span>
        <h3 class="weather-city">{{ city.name }}</h3>
      </div>
      <div v-if="forecast" class="weather-current">
        <WeatherIcon class="weather-current-icon" :kind="currentCondition.icon" />
        <div class="weather-current-values">
          <div class="weather-temperature">{{ temperatureText(forecast.temperature, '') }}<span>°C</span></div>
          <div class="weather-condition">{{ currentCondition.label }}</div>
        </div>
      </div>
      <button
        ref="switchButton"
        type="button"
        class="weather-button weather-switch"
        :aria-expanded="searchOpen"
        @click.stop="toggleSearch"
      >{{ searchOpen ? '收起搜索' : '切换城市' }}</button>
    </header>

    <div v-if="searchOpen" class="weather-search" @keydown.esc.stop.prevent="closeSearch">
      <form
        class="weather-search-form"
        @submit.prevent="runSearch"
        @mousedown.stop
        @touchstart.stop
        @click.stop
      >
        <input
          ref="searchInput"
          v-model="searchQuery"
          type="search"
          class="weather-input"
          aria-label="搜索城市"
          placeholder="例如：北京、上海"
          autocomplete="off"
          @input="clearSearchResults"
        >
        <button class="weather-button" type="submit" :disabled="searchLoading">搜索</button>
      </form>

      <p v-if="searchLoading" class="weather-feedback" role="status">正在搜索城市…</p>
      <div v-else-if="searchError" class="weather-feedback" role="alert">
        <p>{{ searchError }}</p>
        <button v-if="searchRetry" type="button" class="weather-button" @click.stop="runSearch">重试</button>
      </div>
      <ul v-else-if="searchOptions.length" class="weather-results" aria-label="城市搜索结果">
        <li v-for="{ result, region } in searchOptions" :key="result.id">
          <button type="button" class="weather-result" @click.stop="selectCity(result)">
            <span>{{ result.name }}</span>
            <span v-if="region" class="weather-result-region">{{ region }}</span>
          </button>
        </li>
      </ul>
    </div>

    <template v-else>
      <p v-if="forecastLoading" class="weather-feedback" role="status">正在获取天气…</p>
      <div v-else-if="forecastError" class="weather-feedback" role="alert">
        <p>{{ forecastError }}</p>
        <button type="button" class="weather-button" @click.stop="refreshForecast">重试</button>
      </div>
      <template v-else-if="forecast">
        <dl class="weather-metrics">
          <div><dt>今日最高</dt><dd>{{ temperatureText(forecast.today.high) }}</dd></div>
          <div><dt>今日最低</dt><dd>{{ temperatureText(forecast.today.low) }}</dd></div>
          <div><dt>湿度</dt><dd>{{ forecast.humidity === null ? '—' : Math.round(forecast.humidity) + '%' }}</dd></div>
        </dl>

        <div class="weather-outlook">
          <h4>未来 3 天</h4>
          <ul class="weather-days">
            <li v-for="day in upcoming" :key="day.date">
              <time :datetime="day.date">{{ shortDate(day.date) }}</time>
              <WeatherIcon class="weather-day-icon" :kind="day.condition.icon" />
              <span class="weather-day-condition">{{ day.condition.label }}</span>
              <div class="weather-day-range">
                <span :aria-label="'最低 ' + temperatureText(day.low)">{{ temperatureText(day.low) }}</span>
                <span aria-hidden="true">/</span>
                <strong :aria-label="'最高 ' + temperatureText(day.high)">{{ temperatureText(day.high) }}</strong>
              </div>
            </li>
          </ul>
        </div>
      </template>
    </template>

    <footer class="weather-source">
      <span>数据来源</span>
      <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer" @click.stop>Open-Meteo</a>
      <a href="https://www.geonames.org/" target="_blank" rel="noopener noreferrer" @click.stop>GeoNames</a>
      <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer" @click.stop>CC BY 4.0</a>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useStore } from '@/store'
import WeatherIcon from './WeatherIcon.vue'
import {
  DEFAULT_CITY,
  cityRegion,
  loadWeatherForecast,
  readWeatherCity,
  searchWeatherCities,
  weatherCityKey,
  weatherCondition,
  weatherErrorText,
  type WeatherCity,
  type WeatherForecast
} from './weather'

const props = defineProps<{
  element?: ComponentOptions
  componentSetting: Record<string, unknown>
  isAction?: boolean
}>()

const store = useStore()
const previewCity = ref<WeatherCity>()
const city = computed(() => previewCity.value ?? readWeatherCity(props.componentSetting?.city) ?? DEFAULT_CITY)
const cardStyle = computed(() => {
  const { textColor, fontFamily, padding } = props.componentSetting ?? {}
  return {
    color: typeof textColor === 'string' && textColor ? textColor : '#f8fafc',
    fontFamily: typeof fontFamily === 'string' && fontFamily ? fontFamily : 'inherit',
    '--weather-padding': (typeof padding === 'number' && Number.isFinite(padding) ? Math.max(0, padding) : 14) + 'px'
  }
})

const forecast = ref<WeatherForecast>()
const forecastLoading = ref(false)
const forecastError = ref('')
const currentCondition = computed(() => weatherCondition(forecast.value?.code ?? null))
const upcoming = computed(() =>
  (forecast.value?.upcoming ?? []).map(day => ({ ...day, condition: weatherCondition(day.code) }))
)

let forecastRequest: AbortController | undefined
let refreshTimer: ReturnType<typeof setTimeout> | undefined

/** 刷新当前城市，切换时取消旧观察，并且只允许当前请求回填卡片。 */
async function refreshForecast() {
  clearTimeout(refreshTimer)
  forecastRequest?.abort()
  const controller = new AbortController()
  forecastRequest = controller
  forecast.value = undefined
  forecastLoading.value = true
  forecastError.value = ''

  try {
    const result = await loadWeatherForecast(city.value, controller.signal)
    if (controller.signal.aborted) return
    forecast.value = result
    // 前台仅在缓存过期后更新，隐藏期间等页面再次可见再请求。
    refreshTimer = setTimeout(refreshWhenVisible, Math.max(0, result.expiresAt - Date.now()))
  } catch (error) {
    if (!controller.signal.aborted) forecastError.value = weatherErrorText(error)
  } finally {
    if (forecastRequest === controller) {
      forecastRequest = undefined
      forecastLoading.value = false
    }
  }
}

/** 重新回到标签页时才刷新已经过期的预报；网络错误由重试按钮处理。 */
function refreshWhenVisible() {
  if (document.visibilityState !== 'visible' || !forecast.value) return
  if (Date.now() >= forecast.value.expiresAt) {
    void refreshForecast()
  }
}

const searchOpen = ref(false)
const searchQuery = ref('')
const searchLoading = ref(false)
const searchError = ref('')
const searchRetry = ref(false)
const searchResults = ref<WeatherCity[]>([])
const searchInput = ref<HTMLInputElement>()
const switchButton = ref<HTMLButtonElement>()
let searchRequest: AbortController | undefined

const searchOptions = computed(() => {
  const results = searchResults.value.map(result => ({ result, region: cityRegion(result) }))
  return results.map(item => {
    const { result, region } = item
    // 寻址结果若连地区层级也重复，用坐标区分具体地点。
    const duplicate = results.some(other => other !== item && other.result.name === result.name && other.region === region)
    return duplicate ? { result, region: [region, [result.latitude, result.longitude].join(', ')].filter(Boolean).join(' · ') } : item
  })
})

/** 修改输入或关闭搜索时取消旧请求，不重新提交未完成的输入。 */
function clearSearchResults() {
  searchRequest?.abort()
  searchRequest = undefined
  searchLoading.value = false
  searchError.value = ''
  searchRetry.value = false
  searchResults.value = []
}

/** 收起搜索后将焦点还给触发按钮。 */
async function closeSearch() {
  clearSearchResults()
  searchOpen.value = false
  searchQuery.value = ''
  await nextTick()
  switchButton.value?.focus()
}

/** 在卡片内打开城市搜索并让键盘直接进入输入框。 */
async function toggleSearch() {
  if (searchOpen.value) {
    await closeSearch()
    return
  }
  searchOpen.value = true
  await nextTick()
  searchInput.value?.focus()
}

/** 仅在显式提交或重试时请求地点，不随用户的每次按键调用服务。 */
async function runSearch() {
  if (searchLoading.value) return
  clearSearchResults()
  const query = searchQuery.value.trim()
  if (Array.from(query).length < 2) {
    searchError.value = '请输入至少两个字符的城市名。'
    searchInput.value?.focus()
    return
  }

  const controller = new AbortController()
  searchRequest = controller
  searchLoading.value = true
  try {
    const results = await searchWeatherCities(query, controller.signal)
    if (controller.signal.aborted) return
    searchResults.value = results
    if (!results.length) {
      searchError.value = '没有找到这个城市，试试完整地名。'
      searchRetry.value = true
    }
  } catch (error) {
    if (!controller.signal.aborted) {
      searchError.value = weatherErrorText(error)
      searchRetry.value = true
    }
  } finally {
    if (searchRequest === controller) {
      searchRequest = undefined
      searchLoading.value = false
    }
  }
}

/** 更新正式物料的城市，弹出卡只写宿主交互里的对应字段，无配置记录的预览只改本地。 */
function selectCity(result: WeatherCity) {
  const id = props.element?.i
  const element = id ? store.list.find(item => item.i === id) ?? store.affix.find(item => item.i === id) : undefined
  const action = element?.actionSetting
  if (element && !props.isAction && element.material === 'WeatherCard') {
    store.editComponent({ ...element, componentSetting: { ...element.componentSetting, city: result } })
  } else if (
    element && props.isAction && store.actionElement?.i === id &&
    action?.actionType === 1 && action.actionClickType === 1 && action.actionClickValue?.material === 'WeatherCard'
  ) {
    // 交互弹层通过嵌套配置持久化，同时更新打开中的弹层，不改宿主卡片自身设置。
    const next = {
      ...element,
      actionSetting: {
        ...action,
        actionClickValue: {
          ...action.actionClickValue,
          componentSetting: { ...action.actionClickValue.componentSetting, city: result }
        }
      }
    }
    store.editComponent(next)
    store.updateActionElement(next)
  } else {
    previewCity.value = result
  }
  void closeSearch()
}

/** 气温统一显示摄氏整数，缺失项保留破折号。 */
function temperatureText(value: number | null, unit = '°') {
  return value === null ? '—' : String(Math.round(value)).replace(/^-/, '−') + unit
}

/** 格式化城市当地日期，不经过浏览器的本地时区。 */
function shortDate(date: string) {
  const [, month, day] = date.split('-')
  return Number(month) + '/' + Number(day)
}

onMounted(() => {
  document.addEventListener('visibilitychange', refreshWhenVisible)
})

watch(() => weatherCityKey(city.value), refreshForecast, { immediate: true })

onUnmounted(() => {
  forecastRequest?.abort()
  searchRequest?.abort()
  clearTimeout(refreshTimer)
  document.removeEventListener('visibilitychange', refreshWhenVisible)
})
</script>

<style scoped>
.weather-card {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  position: relative;
  width: 100%;
  min-width: 0;
  height: 100%;
  padding: min(var(--weather-padding, 16px), 6%);
  gap: 12px;
  overflow: auto;
  scrollbar-width: thin;
  scrollbar-color: rgba(203, 222, 239, 0.35) transparent;
  border: none;
  border-radius: 0;
  background: transparent;
  color-scheme: dark;
  font-size: 13px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.weather-header,
.weather-current,
.weather-search-form,
.weather-feedback,
.weather-source {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.weather-header { gap: 7px 12px; }
.weather-place { flex: 1 1 auto; min-width: 0; max-width: 100%; }
.weather-kicker { font-size: 11px; opacity: 0.78; }
.weather-city { margin: 1px 0 0; font-size: 18px; line-height: 1.2; }
.weather-current { min-width: 0; gap: 5px; }
.weather-current-icon {
  width: 30px;
  height: 30px;
  filter: drop-shadow(0 6px 14px rgba(0, 0, 0, 0.28));
}
.weather-temperature {
  font-size: clamp(26px, 4vw, 34px);
  line-height: 1;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.weather-temperature span { margin-left: 2px; font-size: 0.5em; font-weight: 500; }
.weather-condition { font-size: 12px; opacity: 0.89; }
.weather-switch { margin-left: auto; }

.weather-button,
.weather-result,
.weather-input {
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  font: inherit;
  color: inherit;
  background: rgba(247, 251, 255, 0.09);
  border: 1px solid rgba(235, 246, 255, 0.18);
  border-radius: 9px;
}
.weather-button { min-height: 32px; padding: 4px 9px; cursor: pointer; overflow-wrap: anywhere; }
.weather-button:hover:not(:disabled), .weather-result:hover { background: rgba(221, 240, 255, 0.19); }
.weather-button:disabled { cursor: default; opacity: 0.62; }
.weather-card:focus-visible,
.weather-card :is(button, input, a):focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 1px;
}
.weather-card:focus-visible { outline-offset: -2px; }
.weather-input { flex: 1 1 9rem; min-height: 34px; padding: 5px 8px; }
.weather-input::placeholder { color: #c4d2e3; }

.weather-search { display: grid; gap: 8px; }
.weather-feedback { margin: 0; padding: 8px; background: rgba(255, 255, 255, 0.06); border-radius: 9px; }
.weather-feedback p { flex: 1 1 12ch; min-width: 0; margin: 0; }
.weather-results, .weather-days { margin: 0; padding: 0; list-style: none; }
.weather-results { display: grid; gap: 5px; }
.weather-result {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 2px 9px;
  width: 100%;
  min-height: 34px;
  padding: 5px 9px;
  text-align: left;
  cursor: pointer;
  overflow-wrap: anywhere;
}
.weather-result-region { max-width: 100%; font-size: 12px; opacity: 0.8; }

.weather-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 70px), 1fr));
  gap: 6px;
  margin: 0;
}
.weather-metrics > div, .weather-days > li {
  min-width: 0;
  padding: 8px 10px;
  background: rgba(15, 23, 42, 0.28);
  border: 1px solid rgba(255, 255, 255, 0.09);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  transition: background 0.16s ease, border-color 0.16s ease;
}
.weather-metrics > div:hover, .weather-days > li:hover {
  background: rgba(15, 23, 42, 0.38);
  border-color: rgba(255, 255, 255, 0.16);
}
.weather-metrics dt { font-size: 11px; opacity: 0.62; }
.weather-metrics dd { margin: 2px 0 0; font-size: 17px; font-weight: 650; font-variant-numeric: tabular-nums; }
.weather-outlook h4 { margin: 0 0 6px; font-size: 12px; font-weight: 600; opacity: 0.72; }
.weather-days {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 75px), 1fr));
  gap: 8px;
}
.weather-days > li { display: grid; justify-items: start; align-content: start; gap: 3px; }
.weather-days time { font-size: 11px; opacity: 0.68; font-variant-numeric: tabular-nums; }
.weather-day-icon { width: 20px; height: 20px; filter: drop-shadow(0 3px 8px rgba(0, 0, 0, 0.24)); }
.weather-day-condition { align-self: start; font-size: 12px; opacity: 0.88; }
.weather-day-range { display: flex; flex-wrap: wrap; gap: 1px 3px; font-variant-numeric: tabular-nums; }
.weather-day-range span { opacity: 0.62; }
.weather-source { gap: 2px 8px; font-size: 11px; opacity: 0.48; }
.weather-source a { color: inherit; text-decoration: underline; text-underline-offset: 2px; }
</style>
