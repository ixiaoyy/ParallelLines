<template>
  <div class="wrapper">
    <div class="export">
      <div class="title">
        {{ $t('配置数据导出') }}
      </div>
      <el-form label-width="80px" label-position="top">
        <el-form-item :label="$t('导出方式')">
          <div class="json-wrapper">
            <button
              type="button"
              class="btn btn-primary"
              style="margin: 0 0 4px"
              @click="handleExportJson"
            >
              {{ $t('导出JSON') }}
            </button>
          </div>
          <p class="helper-text">
            所有配置仅保存在本地浏览器，可通过 JSON 文件随时备份或在多设备间手动迁移。
          </p>
        </el-form-item>
      </el-form>
    </div>
    <hr class="hr">
    <div class="import">
      <div class="title">
        {{ $t('配置数据导入') }}
      </div>
      <el-form label-width="80px" label-position="top">
        <el-form-item :label="$t('导入方式')">
          <div class="json-wrapper">
            <button
              type="button"
              class="btn btn-primary"
              style="margin-left: 0"
              @click="handleUploadJSON"
            >
              {{ $t('上传JSON文件') }}
            </button>
            <input ref="jsonRef" type="file" accept=".json" style="display: none">
          </div>
          <p class="helper-text">
            导入时会自动按安全白名单过滤不受支持的组件与脚本字段。
          </p>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import { useStore } from '@/store'
import { saveAs } from 'file-saver'
import { ElNotification } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { sanitizeDashboardPayload } from '@/parallellines/security'

const store = useStore()
const jsonRef = ref<HTMLInputElement>()
const { t } = useI18n()

const handleExportJson = () => {
  try {
    const {
      list,
      affix,
      global,
      showBackgroundEffect,
      showRefreshBtn,
      tabList,
      showTabSwitchBtn,
      enableKeydownSwitchTab,
      backgroundEffectActive
    } = store
    const dataToString = JSON.stringify(
      {
        list,
        affix,
        global,
        showBackgroundEffect,
        showRefreshBtn,
        tabList,
        showTabSwitchBtn,
        enableKeydownSwitchTab,
        backgroundEffectActive
      },
      null,
      2
    )
    saveAs(
      new Blob([dataToString], { type: 'application/json;charset=utf-8;' }),
      'ParallelLines-Desk.json'
    )
  } catch (e) {
    console.error(e)
  }
}

const updateConfig = (raw: any) => {
  const { payload, removedCount } = sanitizeDashboardPayload(raw)
  store.updateStates([
    { key: 'tabList', value: payload.tabList },
    { key: 'list', value: payload.list },
    { key: 'affix', value: payload.affix },
    { key: 'showBackgroundEffect', value: payload.showBackgroundEffect },
    { key: 'showRefreshBtn', value: payload.showRefreshBtn },
    { key: 'showTabSwitchBtn', value: payload.showTabSwitchBtn },
    { key: 'enableKeydownSwitchTab', value: payload.enableKeydownSwitchTab },
    { key: 'backgroundEffectActive', value: payload.backgroundEffectActive }
  ])
  store.updateGlobal(payload.global)
  ElNotification({
    title: t('提示'),
    type: removedCount > 0 ? 'warning' : 'success',
    message:
      removedCount > 0
        ? `导入成功，已按安全策略自动过滤 ${removedCount} 个不受支持的组件`
        : t('导入配置成功')
  })
}

const handleUploadJSON = () => {
  if (!jsonRef.value) return
  jsonRef.value.value = ''
  jsonRef.value.click()
  jsonRef.value.onchange = (e: Event) => {
    const errorHandler = () => {
      ElNotification({
        title: t('异常'),
        type: 'error',
        message: t('识别文件错误，请检查文件')
      })
    }
    const el = e.currentTarget as HTMLInputElement | null
    const file = el?.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.readAsText(file, 'UTF-8')
    reader.onload = (e1) => {
      const jsonFileData = e1.target?.result
      try {
        const json = JSON.parse(String(jsonFileData || ''))
        if (confirm('识别文件成功，导入将覆盖当前本地工作台配置，是否继续？')) {
          updateConfig(json)
        }
      } catch {
        errorHandler()
      }
    }
    reader.onerror = () => errorHandler()
  }
}
</script>
<style lang="scss" scoped>
.wrapper {
  padding: 10px;
  .export,
  .import {
    .title {
      color: $color-grey1;
      margin-bottom: 8px;
      position: relative;
      font-weight: bold;
      display: inline-block;
      &:after {
        position: absolute;
        content: '';
        left: 0;
        width: 100%;
        bottom: 0;
        height: 8px;
        background: rgba(233, 174, 49, 0.2);
      }
    }
    .json-wrapper {
      margin: 10px 0 6px;
      width: 100%;
      display: flex;
      align-items: center;
      flex-wrap: wrap;
    }
    .helper-text {
      margin: 4px 0 0;
      font-size: 12px;
      line-height: 1.5;
      color: #6b7280;
    }
  }
  :deep(.el-form-item__label) {
    padding-bottom: 0;
  }
}
.hr {
  margin: 20px 0;
  border: 1px solid #e5e7eb;
}
</style>
