import { createApp } from 'vue'
import VueGridLayout from 'vue-grid-layout'
import { i18n } from '@/lang'
import App from './App.vue'
import store from './store'
import '@/assets/element-modules.scss'
import '@/assets/global.scss'
import '@/parallellines/bonjourr-theme.scss'
import {
  ElRadioGroup,
  ElRadio,
  ElInput,
  ElOption,
  ElSelect,
  ElForm,
  ElFormItem,
  ElInputNumber,
  ElIcon,
  ElColorPicker,
  ElSwitch,
  ElTooltip,
  ElAlert,
  ElCheckbox,
  ElImage,
  ElTabs,
  ElTabPane,
  ElDatePicker
} from 'element-plus'
import EasyDialog from '@/components/Global/EasyDialog.vue'
import Icon from '@/components/Tools/Icon.vue'

// 非Edge滚动条重置
if (!window.navigator.userAgent.includes('Edg/')) {
  document.body.classList.add('scrollbar1')
}

const init = () => {
  const app = createApp(App)
  app.use(store)
  app.use(i18n)

  const components = [
    ElRadioGroup,
    ElRadio,
    ElInput,
    ElOption,
    ElSelect,
    ElForm,
    ElFormItem,
    ElInputNumber,
    ElIcon,
    ElColorPicker,
    ElSwitch,
    ElTooltip,
    ElAlert,
    ElCheckbox,
    ElImage,
    ElTabs,
    ElTabPane,
    ElDatePicker,
  ]
  components.forEach((component) => {
    app.use(component)
  })
  app.use(VueGridLayout)
  app.component('EasyDialog', EasyDialog)
  app.component('Icon', Icon)

  const globalLoading = document.querySelector('#globalLoading')
  if (globalLoading) {
    globalLoading.parentNode?.removeChild(globalLoading)
  }
  app.mount('#app')
}

init()

// 移动端禁用右键菜单与长按选中
if ('ontouchstart' in window) {
  document.documentElement.style.setProperty('--user-select', 'none')
  document.addEventListener('contextmenu', (e) => e.preventDefault())
}
