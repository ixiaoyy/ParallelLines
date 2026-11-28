<template>
  <div
    class="wrapper material-clock"
    :style="{
      color: componentSetting.textColor || '#f8fafc',
      padding: (componentSetting.padding ?? 0) + 'px',
      fontFamily: componentSetting.fontFamily,
      ...positionCSS
    }"
  >
    <div class="clock-stack">
      <div
        class="clock-digits"
        :style="{
          fontSize: (componentSetting.textFontSize || 82) + 'px',
          textShadow: componentSetting.textShadow,
          ...textHollowStyle
        }"
      >
        {{ now }}
      </div>
      <div class="clock-meta">
        <span>{{ dateLabel }}</span>
        <span class="clock-sep" aria-hidden="true">·</span>
        <span>{{ greeting }}</span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, onUnmounted, ref, computed, watch } from 'vue'
import { mapPosition } from '@/plugins/position-selector'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

export default defineComponent({
  name: 'Clock',
  props: {
    componentSetting: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const now = ref('')
    const dateLabel = ref('')
    const greeting = ref('')

    function syncTime() {
      const d = new Date()
      const h = d.getHours()
      const m = d.getMinutes()
      now.value = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
      dateLabel.value = `${d.getMonth() + 1}月${d.getDate()}日 ${WEEKDAYS[d.getDay()]}`
      if (h < 6) greeting.value = '夜深了'
      else if (h < 12) greeting.value = '上午好'
      else if (h < 14) greeting.value = '中午好'
      else if (h < 18) greeting.value = '下午好'
      else greeting.value = '晚上好'
    }

    let timer: number
    function init() {
      syncTime()
      timer = window.setInterval(syncTime, props.componentSetting?.duration || 5000)
    }

    init()
    watch(() => props.componentSetting.duration, () => {
      window.clearInterval(timer)
      init()
    })

    onUnmounted(() => {
      window.clearInterval(timer)
    })

    const positionCSS = computed(() => mapPosition(props.componentSetting.position))
    const textHollowStyle = computed(() => props.componentSetting.textHollow ? {
      '-webkit-text-fill-color': props.componentSetting.textHollowBg,
      '-webkit-text-stroke': `${props.componentSetting.textHollowBorder}px ${props.componentSetting.textColor}`
    } : {})

    return {
      now,
      dateLabel,
      greeting,
      positionCSS,
      textHollowStyle
    }
  }
})
</script>
<style lang="scss" scoped>
.wrapper {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  user-select: none;
}

.clock-stack {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.clock-digits {
  font-weight: 600;
  line-height: 1;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
}

.clock-meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: clamp(13px, 1.3vw, 15px);
  font-weight: 500;
  letter-spacing: 0.04em;
  opacity: 0.78;
  text-shadow: 0 2px 12px rgba(15, 23, 42, 0.45);
}

.clock-sep {
  opacity: 0.55;
}
</style>
