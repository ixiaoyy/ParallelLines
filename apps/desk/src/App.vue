<template>
  <div
    v-mouse-menu="mouseMenuOptions"
    class="page"
    :style="global.globalFontFamily && `font-family: ${global.globalFontFamily}`"
  >
    <BackgroundImage ref="bg" :background="global.background" :filter="global.backgroundFilter" />
    <BackgroundEffect />
    <DeskQuickBar @add-component="showAddDialog" />
    <GooeyMenu
      v-if="global.showMenuBtn !== false || isMobile"
      @add-component="showAddDialog"
      @show-global-config="showGlobalConfig"
      @show-auxiliary-config="showAuxiliaryConfig"
    />
    <Layout @edit="showEditDialog" />
    <BaseConfig ref="baseConfig" />
    <GlobalConfig v-model:visible="globalConfigVisible" />
    <AuxiliaryConfig v-model:visible="axuiliaryConfigVisible" />
    <TabCarousel />
  </div>
</template>
<script lang="ts" setup>
import { ref, computed, h, onMounted, onUnmounted } from 'vue'
import Layout from '@/components/Layout.vue'
import BaseConfig from '@/components/BaseConfig.vue'
import GooeyMenu from '@/components/GooeyMenu.vue'
import GlobalConfig from '@/components/GlobalConfig.vue'
import BackgroundImage from '@/components/Global/BackgroundImage.vue'
import BackgroundEffect from '@/components/Global/BackgroundEffect.vue'
import AuxiliaryConfig from '@/components/AuxiliaryConfig.vue'
import TabCarousel from './components/Global/TabCarousel.vue'
import vMouseMenu from '@/plugins/mouse-menu'
import { useStore } from '@/store'
import { useI18n } from 'vue-i18n'
import { uid, isIOSSafari } from '@/utils'
import { svgBase64ToPng } from '@/utils/images'
import Icon from '@/components/Tools/Icon.vue'
import { ElNotification } from 'element-plus'
import {
  createParallelLinesDefaultPreset,
  DEFAULT_PRESET_VERSION
} from '@/parallellines/default-preset'
import { sanitizeComponent, sanitizeComponentList, sanitizeGlobal } from '@/parallellines/security'
import { handleIncomingPinShortcut } from '@/parallellines/pinShortcut'
import DeskQuickBar from '@/parallellines/components/DeskQuickBar.vue'
import { startCloudSync } from '@/parallellines/cloudSync'
const store = useStore()
const global = computed(() => store.global)
const isLock = computed(() => store.isLock)
const { t } = useI18n()

const isMobile = 'ontouchstart' in window

if (global.value.siteTitle) {
  document.title = global.value.siteTitle
}
if (global.value.siteIcon) {
  const iconDom = document.querySelector("link[rel='icon']") as HTMLLinkElement
  if (iconDom) {
    iconDom.href = global.value.siteIcon
  }
}

const bg = ref()

const baseConfig = ref()
const showAddDialog = () => {
  baseConfig.value.open()
}
const showEditDialog = (id: string) => {
  baseConfig.value.open(id)
}

const globalConfigVisible = ref(false)
const showGlobalConfig = () => {
  globalConfigVisible.value = true
}

const axuiliaryConfigVisible = ref(false)
const showAuxiliaryConfig = () => {
  axuiliaryConfigVisible.value = true
}

const handleDownloadBg = () => {
  const url = document.querySelector('.global-bg-img')?.getAttribute('src')
  if (url) {
    // 当前因非同域名图片不能直接下载，会新窗口打开
    const a = document.createElement('a')
    a.setAttribute('href', url)
    a.setAttribute('download', 'background')
    a.setAttribute('target', '_blank')
    a.click()
  }
}

const menuList = ref([
  {
    label: () => t('添加组件'),
    fn: () => {
      showAddDialog()
    },
    icon: h(Icon, { name: 'add', size: 20 })
  },
  {
    label: () => t('全局设置'),
    fn: () => {
      showGlobalConfig()
    },
    icon: h(Icon, { name: 'setting-4', size: 18 })
  },
  {
    label: () => t('辅助功能'),
    fn: () => {
      showAuxiliaryConfig()
    },
    icon: h(Icon, { name: 'tools', size: 18 })
  },
  {
    line: true
  },
  {
    label: () => t('刷新壁纸'),
    hidden: () => !global.value.background.includes('api/randomPhoto'),
    fn: () => {
      bg.value.refresh()
    },
    icon: h(Icon, { name: 'refresh', size: 18 })
  },
  {
    label: () => t('下载壁纸'),
    hidden: () => !global.value.background.includes('api/randomPhoto'),
    fn: () => {
      handleDownloadBg()
    },
    icon: h(Icon, { name: 'download-cloud', size: 18 })
  },
  {
    line: true,
    hidden: () => !global.value.background.includes('api/randomPhoto')
  },
  {
    label: () => t('粘贴'),
    hidden: () => isLock.value,
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
    label: () => (isLock.value ? t('进入编辑') : t('锁定')),
    fn: () => {
      store.updateIsLock(!isLock.value)
    },
    icon: () =>
      isLock.value ? h(Icon, { name: 'unlock', size: 18 }) : h(Icon, { name: 'lock', size: 18 })
  }
])

const mouseMenuOptions = computed(() => ({
  menuList: menuList.value,
  disabled: (params, clickDom) => {
    const isLongPressBookmark = isMobile && !!clickDom.closest('.material-bookmark .item')
    return isLongPressBookmark || (isMobile && !isLock.value)
  },
  iconType: 'vnode-icon'
}))

// 启动时对本地持久化的组件与全局配置执行一次白名单净化；若为空或仍是旧版默认原型则加载 v2 舒展布局
const cleanList = sanitizeComponentList(store.list).items
const cleanAffix = sanitizeComponentList(store.affix).items
const savedPresetVersion = localStorage.getItem('pl_desk_preset_version')
const shouldApplyDefaultPreset =
  (cleanList.length === 0 && cleanAffix.length === 0 && (!store.tabList || store.tabList.length <= 1)) ||
  savedPresetVersion !== DEFAULT_PRESET_VERSION

if (shouldApplyDefaultPreset) {
  const preset = createParallelLinesDefaultPreset()
  store.updateStates([
    { key: 'tabList', value: preset.tabList },
    { key: 'list', value: preset.list },
    { key: 'affix', value: preset.affix },
    { key: 'showBackgroundEffect', value: preset.showBackgroundEffect },
    { key: 'showRefreshBtn', value: preset.showRefreshBtn },
    { key: 'showTabSwitchBtn', value: preset.showTabSwitchBtn },
    { key: 'enableKeydownSwitchTab', value: preset.enableKeydownSwitchTab },
    { key: 'backgroundEffectActive', value: preset.backgroundEffectActive }
  ])
  store.updateGlobal(preset.global as any)
  localStorage.setItem('pl_desk_preset_version', DEFAULT_PRESET_VERSION)
} else {
  if (cleanList.length !== store.list.length) store.updateList(cleanList)
  if (cleanAffix.length !== store.affix.length) store.updateAffix(cleanAffix)
  store.updateGlobal(sanitizeGlobal(store.global))
}

let stopCloudSync: (() => void) | undefined
onUnmounted(() => stopCloudSync?.())
onMounted(async () => {
  handleIncomingPinShortcut(store)
  stopCloudSync = startCloudSync(store)
  // IOS Safari icon不支持svg特殊处理成png
  if (isIOSSafari() && global.value.siteIcon) {
    const appleTouchIconDom = document.querySelector("link[rel='apple-touch-icon']") as HTMLLinkElement
    if (appleTouchIconDom) {
      appleTouchIconDom.href = await svgBase64ToPng(global.value.siteIcon, 256)
    }
  }
})
</script>
<style lang="scss" scoped>
.page {
  width: 100%;
  min-height: 100%;
  position: relative;
}
</style>
