<template>
  <svg
    class="weather-icon"
    :class="'weather-icon-' + kind"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.6"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
  >
    <g v-if="kind === 'sun'">
      <circle cx="12" cy="12" r="4.1" />
      <path d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4m0-14.2-1.4 1.4M6.3 17.7l-1.4 1.4" />
    </g>
    <g v-else-if="kind === 'partly'">
      <path d="M6 12a4.2 4.2 0 1 1 7.7-3.1M8.3 2.7V1.5M3.9 4.1 3 3.2M2.7 8.6H1.5m11.4-4.5.9-.9" class="weather-sun-ray" />
      <path d="M8.9 19.5h9.5a3.6 3.6 0 0 0 .1-7.2 5.1 5.1 0 0 0-9.6 1.5 2.9 2.9 0 0 0 0 5.7Z" />
    </g>
    <g v-else-if="kind === 'unknown'">
      <circle cx="12" cy="12" r="8" />
      <path d="M10 9a2 2 0 1 1 3.4 1.6c-.7.6-1.4 1.1-1.4 2m0 3.3v.1" />
    </g>
    <g v-else>
      <path d="M6.4 15h12.1a3.4 3.4 0 0 0 .2-6.8 5.7 5.7 0 0 0-10.8 1.1 3.1 3.1 0 1 0-1.5 5.7Z" />
      <path v-if="kind === 'fog'" d="M4.5 18h14m-10 3h12" />
      <path v-else-if="kind === 'rain'" d="m8 18-1.5 3m6-3L11 21m6-3-1.5 3" />
      <path v-else-if="kind === 'snow'" d="M7 18v.2m5 2.6v.2m5-3v.2" stroke-width="2.4" />
      <path v-else-if="kind === 'storm'" d="m12 16-2.3 3.1h3L11.2 22" />
    </g>
  </svg>
</template>

<script setup lang="ts">
import type { WeatherIconKind } from './weather'

defineProps<{ kind: WeatherIconKind }>()
</script>

<style scoped>
.weather-icon { display: block; color: #bfdbfe; }
.weather-icon-sun, .weather-sun-ray { color: #fcd38a; }
.weather-icon-rain, .weather-icon-storm { color: #a5d7fa; }
.weather-icon-snow { color: #e2f4ff; }
</style>
