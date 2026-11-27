export interface WeatherCity {
  id: number
  name: string
  latitude: number
  longitude: number
  admin1?: string
  admin2?: string
  admin3?: string
  country?: string
}

interface ForecastDay {
  date: string
  code: number | null
  high: number | null
  low: number | null
}

export interface WeatherForecast {
  temperature: number
  humidity: number | null
  code: number | null
  today: ForecastDay
  upcoming: ForecastDay[]
  expiresAt: number
}

export const DEFAULT_CITY: WeatherCity = {
  id: 1816670,
  name: '北京',
  latitude: 39.9075,
  longitude: 116.39723,
  admin1: '北京市',
  country: '中国'
}

export const WEATHER_TTL = 30 * 60 * 1000
const REQUEST_TIMEOUT = 8000
const DAY_MS = 24 * 60 * 60 * 1000
const CACHE_KEY = 'pl_desk_weather_forecast_v1'
const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast'
const GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'

type Failure = 'offline' | 'network' | 'timeout' | 'server' | 'invalid'

class WeatherError extends Error {
  constructor(readonly reason: Failure) {
    super(reason)
    this.name = 'WeatherError'
  }
}

interface PendingForecast {
  controller: AbortController
  promise: Promise<WeatherForecast>
  subscribers: number
}

const pendingForecasts = new Map<string, PendingForecast>()

const record = (value: unknown): Record<string, unknown> | undefined =>
  value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined

const numberOrNull = (value: unknown) =>
  typeof value === 'number' && Number.isFinite(value) ? value : null

const readText = (value: unknown) => typeof value === 'string' ? value.trim() : ''

/** 将地点配置或搜索响应收敛到可显示、可请求且稳定标识的城市记录。 */
export function readWeatherCity(value: unknown): WeatherCity | undefined {
  const city = record(value)
  if (!city) return
  const { id, latitude, longitude } = city
  const name = readText(city.name)
  if (
    typeof id !== 'number' || !Number.isSafeInteger(id) || id < 1 || !name ||
    typeof latitude !== 'number' || !Number.isFinite(latitude) || Math.abs(latitude) > 90 ||
    typeof longitude !== 'number' || !Number.isFinite(longitude) || Math.abs(longitude) > 180
  ) return

  return {
    id, name, latitude, longitude,
    admin1: readText(city.admin1) || undefined,
    admin2: readText(city.admin2) || undefined,
    admin3: readText(city.admin3) || undefined,
    country: readText(city.country) || undefined
  }
}

/** 用地区层级区分同名地点，排除重复显示的市名、区名。 */
export function cityRegion(city: WeatherCity): string {
  const labels = [city.admin3, city.admin2, city.admin1, city.country]
  return [...new Set(labels.filter(label => label && label !== city.name))].join(' · ')
}

/** GeoNames ID 区分同名城市，坐标防止被手工修改的配置命中原地点的缓存。 */
export function weatherCityKey(city: WeatherCity): string {
  return [city.id, city.latitude, city.longitude].join(':')
}

/** 向用户区分连接、限时请求和服务响应异常，保留下一步重试入口。 */
export function weatherErrorText(error: unknown): string {
  switch (error instanceof WeatherError ? error.reason : undefined) {
    case 'offline': return '网络已断开，请联网后重试。'
    case 'timeout': return '连接天气服务超时，请重试。'
    case 'server': return '天气服务暂时不可用，请稍后重试。'
    case 'invalid': return '天气服务返回的数据不完整，请稍后重试。'
    default: return '无法连接天气服务，请检查网络后重试。'
  }
}

/** 仅调用固定的公开地址；限时覆盖连接、响应及读取正文，离开时同步取消。 */
async function requestJson(url: string, params: URLSearchParams, signal: AbortSignal): Promise<unknown> {
  if (signal.aborted) throw new DOMException('请求已取消', 'AbortError')
  if (typeof navigator !== 'undefined' && navigator.onLine === false) throw new WeatherError('offline')

  const controller = new AbortController()
  const cancel = () => controller.abort()
  signal.addEventListener('abort', cancel, { once: true })
  let timedOut = false
  const timeout = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, REQUEST_TIMEOUT)

  try {
    const response = await fetch(url + '?' + params.toString(), {
      signal: controller.signal,
      credentials: 'omit',
      referrerPolicy: 'no-referrer'
    })
    if (!response.ok) throw new WeatherError('server')
    return await response.json()
  } catch (error) {
    if (signal.aborted) throw error
    if (timedOut) throw new WeatherError('timeout')
    if (error instanceof WeatherError) throw error
    if (error instanceof SyntaxError) throw new WeatherError('invalid')
    throw new WeatherError('network')
  } finally {
    clearTimeout(timeout)
    signal.removeEventListener('abort', cancel)
  }
}

/** 显式提交城市名时请求中文搜索结果，保留未找到与服务异常各自的状态。 */
export async function searchWeatherCities(query: string, signal: AbortSignal): Promise<WeatherCity[]> {
  const payload = record(await requestJson(GEOCODING_URL, new URLSearchParams({
    name: query, count: '8', language: 'zh'
  }), signal))

  if (!payload || payload.error || (payload.results !== undefined && !Array.isArray(payload.results))) {
    throw new WeatherError('invalid')
  }
  if (!Array.isArray(payload.results)) return []

  const cities = payload.results.map(readWeatherCity).filter((city): city is WeatherCity => !!city)
  if (payload.results.length && !cities.length) throw new WeatherError('invalid')
  return [...new Map(cities.map(city => [city.id, city])).values()]
}

/** 从城市当地的逐日数据里取当天和随后的三天，不用访问者时区换算日期。 */
function decodeForecast(payload: unknown, fetchedAt: number): WeatherForecast | undefined {
  const source = record(payload)
  const current = record(source?.current)
  const daily = record(source?.daily)
  if (source?.error || !current || !daily) return

  const temperature = numberOrNull(current.temperature_2m)
  const reportedDate = typeof current.time === 'string' ? current.time.slice(0, 10) : ''
  const offsetSeconds = numberOrNull(source?.utc_offset_seconds)
  const offsetMs = offsetSeconds !== null && Math.abs(offsetSeconds) < DAY_MS / 1000 ? offsetSeconds * 1000 : null
  // 以天气服务返回的城市时差判定换日；缺少时差时仍能用响应的当地日期。
  const date = offsetMs === null ? reportedDate : new Date(fetchedAt + offsetMs).toISOString().slice(0, 10)
  const nextMidnight = offsetMs === null ? Infinity : Date.parse(date + 'T00:00:00Z') + DAY_MS - offsetMs
  const expiresAt = Math.min(fetchedAt + WEATHER_TTL, nextMidnight)
  const { time, weather_code, temperature_2m_max, temperature_2m_min } = daily
  if (
    temperature === null || !/^\d{4}-\d{2}-\d{2}$/.test(date) ||
    !Array.isArray(time) || !Array.isArray(weather_code) ||
    !Array.isArray(temperature_2m_max) || !Array.isArray(temperature_2m_min)
  ) return

  const start = time.indexOf(date)
  const localDates = start < 0 ? [] : time.slice(start, start + 4)
  if (localDates.length !== 4 || !localDates.every(day => typeof day === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(day))) return

  // 单项数据缺失用破折号或未知状态，不把 null 当作 0 度、0% 或晴天。
  const days = localDates.map((day, index): ForecastDay => ({
    date: day,
    code: numberOrNull(weather_code[start + index]),
    high: numberOrNull(temperature_2m_max[start + index]),
    low: numberOrNull(temperature_2m_min[start + index])
  }))
  const humidity = numberOrNull(current.relative_humidity_2m)

  return {
    temperature,
    humidity: humidity !== null && humidity >= 0 && humidity <= 100 ? humidity : null,
    code: numberOrNull(current.weather_code),
    today: days[0],
    upcoming: days.slice(1),
    expiresAt
  }
}

function readCache(): Record<string, unknown> {
  try {
    return record(JSON.parse(localStorage.getItem(CACHE_KEY) || '{}')) || {}
  } catch {
    // 存储被禁用或缓存损坏时视为未命中，不影响正常请求。
    return {}
  }
}

function freshEntry(value: unknown, now: number) {
  const entry = record(value)
  const savedAt = numberOrNull(entry?.savedAt)
  const expiresAt = numberOrNull(entry?.expiresAt)
  if (savedAt === null || now < savedAt || now - savedAt >= WEATHER_TTL || (expiresAt !== null && now >= expiresAt)) return
  return { savedAt, payload: entry?.payload }
}

/** 写入当前城市天气，同时移除过期数据；存储不可用时当前结果仍可查看。 */
function cacheForecast(key: string, payload: unknown, savedAt: number, expiresAt: number) {
  try {
    const entries = readCache()
    for (const [entryKey, entry] of Object.entries(entries)) {
      if (!freshEntry(entry, savedAt)) delete entries[entryKey]
    }
    entries[key] = { savedAt, expiresAt, payload }
    localStorage.setItem(CACHE_KEY, JSON.stringify(entries))
  } catch {
    // localStorage 容量不足或被禁用时，缓存写入失败不使天气请求失败。
  }
}

async function requestForecast(city: WeatherCity, key: string, signal: AbortSignal) {
  const payload = await requestJson(FORECAST_URL, new URLSearchParams({
    latitude: String(city.latitude),
    longitude: String(city.longitude),
    current: 'temperature_2m,relative_humidity_2m,weather_code',
    daily: 'weather_code,temperature_2m_max,temperature_2m_min',
    timezone: 'auto',
    forecast_days: '4'
  }), signal)

  const fetchedAt = Date.now()
  const forecast = decodeForecast(payload, fetchedAt)
  if (!forecast) throw new WeatherError('invalid')
  cacheForecast(key, payload, fetchedAt, forecast.expiresAt)
  return forecast
}

/** 按城市优先读 30 分钟缓存，合并同城并发；最后一个调用方离开时才取消共享请求。 */
export async function loadWeatherForecast(city: WeatherCity, signal: AbortSignal): Promise<WeatherForecast> {
  if (signal.aborted) throw new DOMException('请求已取消', 'AbortError')
  const key = weatherCityKey(city)
  const cached = freshEntry(readCache()[key], Date.now())
  const known = cached && decodeForecast(cached.payload, cached.savedAt)
  if (known && Date.now() < known.expiresAt) return known

  let request = pendingForecasts.get(key)
  if (!request) {
    const controller = new AbortController()
    const promise = requestForecast(city, key, controller.signal).finally(() => {
      if (pendingForecasts.get(key)?.controller === controller) pendingForecasts.delete(key)
    })
    request = { controller, promise, subscribers: 0 }
    pendingForecasts.set(key, request)
  }

  const current = request
  current.subscribers += 1
  let cancel: () => void = () => {}
  try {
    return await new Promise<WeatherForecast>((resolve, reject) => {
      cancel = () => reject(new DOMException('请求已取消', 'AbortError'))
      signal.addEventListener('abort', cancel, { once: true })
      current.promise.then(resolve, reject)
    })
  } finally {
    signal.removeEventListener('abort', cancel)
    current.subscribers -= 1
    if (!current.subscribers && pendingForecasts.get(key) === current) {
      pendingForecasts.delete(key)
      current.controller.abort()
    }
  }
}

export type WeatherIconKind = 'sun' | 'partly' | 'cloud' | 'fog' | 'rain' | 'snow' | 'storm' | 'unknown'

/** 将 Open-Meteo 的 WMO 天气代码映射为中文状态与可共享的本地图标。 */
export function weatherCondition(code: number | null): { label: string; icon: WeatherIconKind } {
  if (code === 0) return { label: '晴', icon: 'sun' }
  if (code === 1 || code === 2) return { label: code === 1 ? '大部晴朗' : '局部多云', icon: 'partly' }
  if (code === 3) return { label: '阴', icon: 'cloud' }
  if (code === 45 || code === 48) return { label: code === 48 ? '冻雾' : '雾', icon: 'fog' }
  if (code === 51 || code === 53 || code === 55) return { label: '毛毛雨', icon: 'rain' }
  if (code === 56 || code === 57 || code === 66 || code === 67) return { label: '冻雨', icon: 'rain' }
  if (code === 61 || code === 63 || code === 65) return { label: '降雨', icon: 'rain' }
  if (code === 71 || code === 73 || code === 75 || code === 77) return { label: '降雪', icon: 'snow' }
  if (code === 80 || code === 81 || code === 82) return { label: '阵雨', icon: 'rain' }
  if (code === 85 || code === 86) return { label: '阵雪', icon: 'snow' }
  if (code === 95 || code === 96 || code === 99) return { label: code === 95 ? '雷暴' : '雷暴伴冰雹', icon: 'storm' }
  return { label: '天气未知', icon: 'unknown' }
}
