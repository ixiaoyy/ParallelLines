<script setup lang="ts">
import { GlobalOutlined } from "@ant-design/icons-vue";

import { currentLocale, localePersistenceAvailable, setLocale, supportedLocales, uiText } from "@/shared/i18n/locale";

/** 原生选择器保留键盘与手机操作；只保存界面语言，不修改账号或跨站身份。 */
function changeLanguage(event: Event): void {
  if (event.target instanceof HTMLSelectElement) setLocale(event.target.value);
}
</script>

<template>
  <div class="language-switcher">
    <label class="language-switcher__control">
      <GlobalOutlined aria-hidden="true" />
      <select :value="currentLocale" :aria-label="uiText('界面语言')" @change="changeLanguage">
        <option v-for="item in supportedLocales" :key="item.value" :value="item.value">{{ item.label }}</option>
      </select>
    </label>
    <span v-if="!localePersistenceAvailable" class="language-switcher__warning" role="status">{{ uiText('语言设置仅在当前页面生效，浏览器未能保存你的选择。') }}</span>
  </div>
</template>

<style scoped>
.language-switcher { position: relative; display: inline-flex; align-items: center; flex-shrink: 0; color: inherit; }
.language-switcher__control { display: inline-flex; align-items: center; gap: 5px; min-height: 44px; }
select { max-width: 112px; min-height: 44px; border: 0; border-radius: 6px; padding: 0 3px; color: inherit; background: transparent; font: inherit; font-size: 13px; cursor: pointer; }
select:focus-visible { outline: 2px solid var(--catalog-focus, var(--focus-ring, #409eff)); outline-offset: 2px; }
.language-switcher__warning { position: absolute; top: 100%; right: 0; z-index: 100; width: 240px; border: 1px solid var(--border, #e2e8f0); border-radius: 8px; padding: 10px; color: var(--text, #475569); background: var(--bg-surface, #fff); font-size: 13px; line-height: 1.5; white-space: normal; box-shadow: 0 6px 20px #0002; }
@media (max-width: 760px) { .language-switcher__control { gap: 1px; } select { max-width: 96px; font-size: 12px; } }
</style>
