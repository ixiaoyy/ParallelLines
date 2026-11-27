<template>
  <div
    v-if="windowWidth > 0 && !isCompactViewport"
    class="grid-wrapper"
    :style="`width: ${windowWidth}px;`"
  >
    <grid-layout
      v-model:layout="list"
      :col-num="12"
      :row-height="rowHeight"
      :margin="[global.gutter, global.gutter]"
      :is-draggable="!isLock"
      :is-resizable="!isLock"
      :use-css-transforms="false"
      @layout-updated="handleLayoutListUpdated"
    >
      <grid-item
        v-for="item in list"
        :id="item.customId || undefined"
        :key="item.i"
        :class="[`grid-item-${item.material}`]"
        :x="item.x"
        :y="item.y"
        :w="item.w"
        :h="item.h"
        :i="item.i"
        :style="{ 'z-index': item.zIndex || 1 }"
      >
        <div
          v-if="!item.refresh"
          v-mouse-menu="{ disabled: () => isLock, params: item, menuList, iconType: 'vnode-icon' }"
          class="item-content"
          :class="!isLock && 'show-outline-1'"
          :style="{
            boxShadow: item.boxShadow,
            borderRadius: item.borderRadius + 'px',
            userSelect: item.actionSetting && item.actionSetting.actionType === 1 ? 'none' : 'auto',
            cursor:
              item.actionSetting && item.actionSetting.actionType === 1 ? 'pointer' : 'default'
          }"
        >
          <div
            class="bg"
            :style="{
              background: item.background,
              borderRadius: item.borderRadius + 'px',
              filter: item.background.includes('url') && item.backgroundFilter,
              backdropFilter: !item.background.includes('url') && item.backdropFilter
            }"
          />
          <component
            :is="item.material"
            :element="item"
            :component-setting="item.componentSetting"
            @click="handleComponentClick(item, $event)"
          />
        </div>
      </grid-item>
    </grid-layout>
  </div>
  <!-- 中窄屏 / 分屏 / 移动端自动切为流式自适应排版，彻底杜绝重叠与截断 -->
  <div v-else-if="windowWidth > 0" class="compact-flow-wrapper">
    <div
      v-for="item in sortedList"
      :id="item.customId || undefined"
      :key="item.i"
      class="compact-flow-item"
      :class="[`grid-item-${item.material}`]"
    >
      <div
        v-if="!item.refresh"
        v-mouse-menu="{ disabled: () => isLock, params: item, menuList, iconType: 'vnode-icon' }"
        class="item-content"
        :class="!isLock && 'show-outline-1'"
        :style="{
          boxShadow: item.boxShadow,
          borderRadius: item.borderRadius + 'px',
          userSelect: item.actionSetting && item.actionSetting.actionType === 1 ? 'none' : 'auto',
          cursor:
            item.actionSetting && item.actionSetting.actionType === 1 ? 'pointer' : 'default'
        }"
      >
        <div
          class="bg"
          :style="{
            background: item.background,
            borderRadius: item.borderRadius + 'px',
            filter: item.background.includes('url') && item.backgroundFilter,
            backdropFilter: !item.background.includes('url') && item.backdropFilter
          }"
        />
        <component
          :is="item.material"
          :element="item"
          :component-setting="item.componentSetting"
          @click="handleComponentClick(item, $event)"
        />
      </div>
    </div>
  </div>
  <div class="affix-wrapper">
    <div
      v-for="element in affix"
      :id="element.customId || undefined"
      :key="element.i"
      v-to-control="{
        positionMode: element.affixInfo ? element.affixInfo.mode : 1,
        moveCursor: false,
        disabled: () => isLock,
        arrowOptions: {
          lineColor: '#9a98c3',
          size: 12,
          padding: 8
        }
      }"
      class="affix-item"
      :class="[!isLock && 'show-outline-2', isToControlFinishedInit && 'finished-init']"
      :style="{
        width: `${element.w}px`,
        height: `${element.h}px`,
        zIndex: element.zIndex || 2,
        ...(element.affixInfo ? computedPosition(element.affixInfo) : {})
      }"
      @todragend="handleAffixDragend($event, element)"
      @tocontrolend="handleAffixDragend($event, element)"
      @todraginit="handleToControlInit"
    >
      <div
        v-if="!element.refresh"
        v-mouse-menu="{ disabled: () => isLock, params: element, menuList, iconType: 'vnode-icon' }"
        class="affix-item-content"
        :style="{
          boxShadow: element.boxShadow,
          borderRadius: element.borderRadius + 'px',
          userSelect:
            element.actionSetting && element.actionSetting.actionType === 1 ? 'none' : 'auto',
          cursor:
            element.actionSetting && element.actionSetting.actionType === 1 ? 'pointer' : 'default'
        }"
      >
        <div
          class="bg"
          :style="{
            background: element.background,
            borderRadius: element.borderRadius + 'px',
            filter: element.background.includes('url') ? element.backgroundFilter : '',
            backdropFilter: !element.background.includes('url') ? element.backdropFilter : ''
          }"
        />
        <component
          :is="element.material"
          :element="element"
          :component-setting="element.componentSetting"
          @click="handleComponentClick(element, $event)"
        />
      </div>
    </div>
  </div>
  <ActionConfig ref="actionConfig" />
  <ActionPopover
    ref="actionPopover"
    :close-on-click-outside="!(actionSetting?.actionType === 1 && actionSetting?.actionClickType === 1 && actionSetting?.actionClickValue?.direction === 0)"
  >
    <div
      v-if="actionElement && actionSetting && actionSetting?.actionType === 1 && actionSetting?.actionClickType === 1"
      class="action-popover-wrapper"
      :style="{
        borderRadius: actionSetting.actionClickValue.borderRadius + 'px',
        boxShadow: actionSetting.actionClickValue.boxShadow
      }"
    >
      <div
        class="bg"
        :style="{
          background: actionSetting.actionClickValue.background,
          filter: actionSetting.actionClickValue.background.includes('url') ? actionSetting.actionClickValue.backgroundFilter : 'none',
          backdropFilter: !actionSetting.actionClickValue.background.includes('url') ? actionSetting.actionClickValue.backdropFilter : ''
        }"
      />
      <component
        :is="actionSetting.actionClickValue.material"
        :element="actionElement"
        :component-setting="actionSetting.actionClickValue.componentSetting"
        is-action
      />
    </div>
  </ActionPopover>
  <Confirm ref="confirmRef" />
</template>

<script lang="ts">
import {
  defineComponent,
  ref,
  computed,
  defineAsyncComponent,
  nextTick,
  onMounted,
  watchEffect,
  h
} from 'vue'
import { useStore } from '@/store'
import { ToControlDirective } from '@howdyjs/to-control'
import MouseMenuDirective from '@/plugins/mouse-menu'
import useScreenMode from '@/hooks/useScreenMode'
import Loading from '@/components/Tools/Loading.vue'
import Icon from '@/components/Tools/Icon.vue'
import { useI18n } from 'vue-i18n'
import { ElNotification } from 'element-plus'
import { uid } from '@/utils'
import { isAllowedMaterial, sanitizeComponent } from '@/parallellines/security'
export default defineComponent({
  name: 'Layout',
  components: {
    ActionConfig: defineAsyncComponent(() => import('@/components/ActionConfig.vue')),
    ActionPopover: defineAsyncComponent(() => import('@/components/Action/ActionPopover.vue')),
    Confirm: defineAsyncComponent(() => import('@/components/Tools/Confirm.vue')),
    Empty: defineAsyncComponent(() => import('@/materials/Empty/index.vue')),
    Clock: defineAsyncComponent(() => import('@/materials/Clock/index.vue')),
    SlackCountdown: defineAsyncComponent(() => import('@/parallellines/materials/SlackCountdown/index.vue')),
    AiSearch: defineAsyncComponent(() => import('@/parallellines/materials/AiSearch/index.vue')),
    WeatherCard: defineAsyncComponent(() => import('@/parallellines/materials/WeatherCard/index.vue')),
    AlarmTimer: defineAsyncComponent(() => import('@/parallellines/materials/AlarmTimer/index.vue')),
    Search: defineAsyncComponent(() => import('@/materials/Search/index.vue')),
    Collection: defineAsyncComponent(() => import('@/materials/Collection/index.vue')),
    CountDown: defineAsyncComponent(() => import('@/materials/CountDown/index.vue')),
    Day: defineAsyncComponent(() => import('@/materials/Day/index.vue')),
    TodoList: defineAsyncComponent({
      loader: () => import('@/materials/TodoList/index.vue'),
      loadingComponent: Loading
    }),
    Editor: defineAsyncComponent({
      loader: () => import('@/materials/Editor/index.vue'),
      loadingComponent: Loading
    }),
    Bookmark: defineAsyncComponent(() => import('@/materials/Bookmark/index.vue')),
  },
  directives: {
    MouseMenu: {
      ...MouseMenuDirective,
      updated: MouseMenuDirective.mounted
    },
    ToControl: ToControlDirective
  },
  emits: ['edit'],
  setup(props, { emit }) {
    const { windowWidth, windowHeight } = useScreenMode()
    const { t } = useI18n()

    const actionConfig = ref()
    const actionPopover = ref()
    const confirmRef = ref()

    const store = useStore()
    const isLock = computed(() => store.isLock)
    const global = computed(() => store.global)

    const list = ref<any[]>([])
    watchEffect(() => {
      list.value = (store.list || []).filter((item: any) => isAllowedMaterial(item?.material))
    })

    const isCompactViewport = computed(() => windowWidth.value < 960)
    const sortedList = computed(() =>
      [...list.value].sort((a, b) => (a.y - b.y) || (a.x - b.x))
    )

    const actionElement = computed(() => store.actionElement)
    const actionSetting = computed(() => actionElement.value?.actionSetting)

    const rowHeight = computed(() => {
      const h = windowHeight.value / 27
      return h > 40 ? 40 : h < 20 ? 20 : h
    })

    const menuList = ref([
      {
        label: (params: ComponentOptions) => `# ${params.material}`,
        customClass: 'title'
      },
      {
        label: () => t('组件编辑'),
        fn: (params: ComponentOptions) => {
          emit('edit', params.i)
        },
        icon: h(Icon, { name: 'edit-box', size: 18 })
      },
      {
        label: () => t('交互配置') as string,
        hidden: (params: ComponentOptions) =>
          !['Empty', 'Clock', 'Verse', 'CountDown', 'Weather'].includes(params.material),
        fn: (params: ComponentOptions) => {
          actionConfig.value.open(params)
        },
        icon: h(Icon, { name: 'equalizer', size: 18 })
      },
      {
        label: () => t('刷新组件'),
        fn: async (params: ComponentOptions & { refresh?: boolean }) => {
          params.refresh = true
          await nextTick()
          params.refresh = false
        },
        icon: h(Icon, { name: 'refresh', size: 18 })
      },
      {
        label: () => t('锁定'),
        fn: () => {
          store.updateIsLock(true)
        },
        icon: h(Icon, { name: 'lock', size: 18 })
      },
      {
        line: true
      },
      {
        label: () => t('复制'),
        fn: async (params: ComponentOptions) => {
          try {
            await navigator.clipboard.writeText(JSON.stringify(params, null, 2))
          } catch (e) {
            ElNotification({ title: t('复制异常'), type: 'error', message: t('请检查权限授权')})
            console.error(e)
          }
        },
        icon: h(Icon, { name: 'copy', size: 18 })
      },
      {
        label: () => t('粘贴'),
        fn: async () => {
          try {
            const res = await navigator.clipboard.readText()
            const componentData = sanitizeComponent(JSON.parse(res))
            if (componentData && componentData.componentSetting) {
              // Fixed模式的组件粘贴时更改下位置防止重叠看不出来
              if (componentData.position === 2) {
                componentData.affixInfo.x = componentData.affixInfo?.x + 20
                componentData.affixInfo.y = componentData.affixInfo?.y + 20
              }
              store.addComponent({ ...componentData, i: uid() })
            } else {
              throw new Error('不受支持或非法的组件数据')
            }
          } catch (e) {
            ElNotification({ title: t('粘贴异常'), type: 'error', message: t('请检查权限授权或复制的数据是否正确')})
            console.error(e)
          }
        },
        icon: h(Icon, { name: 'clipboard', size: 18 })
      },
      {
        line: true
      },
      {
        label: () => t('删除'),
        fn: async (params: ComponentOptions) => {
          try {
            await confirmRef.value.confirm(`❗ ${t('确定删除吗')}?`, { height: 150 })
            store.deleteComponent(params)
          } catch {
            //
          }
        },
        icon: h(Icon, { name: 'delete', size: 18 }),
        customClass: 'delete'
      }
    ])

    const affix = computed(() =>
      (store.affix || []).filter((item: any) => isAllowedMaterial(item?.material))
    )
    const computedPosition = ({ mode, x, y }: AffixInfo) => {
      const result = {
        top: 'auto',
        left: 'auto',
        bottom: 'auto',
        right: 'auto'
      }
      if ([1, 2].includes(mode)) {
        result.top = y + 'px'
      } else {
        result.bottom = y + 'px'
      }
      if ([1, 3].includes(mode)) {
        result.left = x + 'px'
      } else {
        result.right = x + 'px'
      }
      return result
    }

    const handleAffixDragend = ($event: any, element: ComponentOptions) => {
      const mode = element.affixInfo?.mode || 1
      const { left, top, bottom, right, width, height } = $event
      const rectInfo = {
        i: element.i,
        x: [1, 3].includes(mode) ? left : right,
        y: [1, 2].includes(mode) ? top : bottom,
        w: width,
        h: height
      }
      store.editAffixRectInfo(rectInfo)
    }

    const handleComponentClick = (component: ComponentOptions, $event: MouseEvent) => {
      if (isLock.value && component.actionSetting && component.actionSetting.actionType === 1) {
        if (component.actionSetting.actionClickType === 1) {
          store.updateActionElement(component)
          actionPopover.value.toggle(component, $event.target)
        } else if (component.actionSetting.actionClickType === 2) {
          const url = component.actionSetting.actionClickValue.url
          window.open(url)
        }
      }
    }

    onMounted(() => {
      try {
        const layoutReady = new CustomEvent('layoutReady')
        window.dispatchEvent(layoutReady)
      } catch {
        //
      }
    })

    const handleLayoutListUpdated = (items: ComponentOptions[]) => {
      // 栅格会回传同一批响应式记录；原地变更已进入 store，重复回写会触发栅格再次更新。
      if (items.length === store.list.length && items.every((item, index) => item === store.list[index])) return
      store.updateList(items)
    }

    const isToControlFinishedInit = ref(false)
    const handleToControlInit = () => {
      if (!isToControlFinishedInit.value) isToControlFinishedInit.value = true
    }

    return {
      windowWidth,
      rowHeight,
      list,
      isCompactViewport,
      sortedList,
      isLock,
      global,
      menuList,
      actionConfig,
      actionPopover,
      actionElement,
      actionSetting,
      confirmRef,
      affix,
      isToControlFinishedInit,
      computedPosition,
      handleAffixDragend,
      handleComponentClick,
      handleLayoutListUpdated,
      handleToControlInit
    }
  }
})
</script>
<style lang="scss" scoped>
.grid-wrapper {
  zoom: 1;
  &:after {
    content: '';
    clear: both;
    display: table;
    height: 0;
  }
  .item-content {
    width: 100%;
    height: 100%;
    position: relative;
    .bg {
      position: absolute;
      width: 100%;
      height: 100%;
      left: 0;
      top: 0;
      background-size: cover;
    }
  }
}
.compact-flow-wrapper {
  width: 100%;
  max-width: 720px;
  margin: 0 auto;
  padding: 20px 14px 72px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 16px;

  .compact-flow-item {
    width: 100%;
  }

  .item-content {
    width: 100%;
    position: relative;
    box-sizing: border-box;

    .bg {
      position: absolute;
      inset: 0;
      background-size: cover;
      pointer-events: none;
    }
  }
}
.flip-list-move {
  transition: transform 0.4s;
}
.affix-wrapper {
  .affix-item {
    position: fixed;
    transition: none !important;
    opacity: 0;
    .affix-item-content {
      width: 100%;
      height: 100%;
      position: relative;
      .bg {
        position: absolute;
        width: 100%;
        height: 100%;
        left: 0;
        top: 0;
        background-size: cover;
      }
    }
    &.finished-init {
      opacity: 1;
    }
  }
}
.action-popover-wrapper {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  .bg {
    position: absolute;
    width: 100%;
    height: 100%;
    left: 0;
    top: 0;
    background-size: cover;
  }
}
.show-outline-1 {
  outline: 2px dashed $color-primary;
  user-select: none;
}
.show-outline-2 {
  outline: 2px dashed $color-warning;
  user-select: none;
  cursor: move;
}
</style>
<style>
.vue-grid-item > .vue-resizable-handle {
  width: 24px !important;
  height: 24px !important;
  background: url('data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBzdGFuZGFsb25lPSJubyI/PjwhRE9DVFlQRSBzdmcgUFVCTElDICItLy9XM0MvL0RURCBTVkcgMS4xLy9FTiIgImh0dHA6Ly93d3cudzMub3JnL0dyYXBoaWNzL1NWRy8xLjEvRFREL3N2ZzExLmR0ZCI+PHN2ZyB0PSIxNjMxNjA4MTYyMzEwIiBjbGFzcz0iaWNvbiIgdmlld0JveD0iMCAwIDEwMjQgMTAyNCIgdmVyc2lvbj0iMS4xIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHAtaWQ9IjMzNjExIiB4bWxuczp4bGluaz0iaHR0cDovL3d3dy53My5vcmcvMTk5OS94bGluayIgd2lkdGg9IjIwMCIgaGVpZ2h0PSIyMDAiPjxkZWZzPjxzdHlsZSB0eXBlPSJ0ZXh0L2NzcyI+PC9zdHlsZT48L2RlZnM+PHBhdGggZD0iTTI4Ni4xNjUzMzMgNjcwLjE2NTMzM2E0Mi42NjY2NjcgNDIuNjY2NjY3IDAgMSAxLTYwLjMzMDY2Ni02MC4zMzA2NjZsMjU2LTI1NmE0Mi42NjY2NjcgNDIuNjY2NjY3IDAgMCAxIDU5LjAwOC0xLjI4bDI1NiAyMzQuNjY2NjY2YTQyLjY2NjY2NyA0Mi42NjY2NjcgMCAxIDEtNTcuNjg1MzM0IDYyLjg5MDY2N2wtMjI1Ljg3NzMzMy0yMDcuMDYxMzMzLTIyNy4xMTQ2NjcgMjI3LjExNDY2NnoiIGZpbGw9IiM5YTk4YzMiIHAtaWQ9IjMzNjEyIj48L3BhdGg+PC9zdmc+')
    0 0/24px 24px !important;
  padding: 0 !important;
  transform: rotate(135deg) !important;
}
</style>
