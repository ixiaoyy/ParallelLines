import pluginVue from "eslint-plugin-vue";
import { defineConfigWithVueTs, vueTsConfigs } from "@vue/eslint-config-typescript";

export default defineConfigWithVueTs(
  {
    ignores: ["dist/**"],
  },
  pluginVue.configs["flat/essential"],
  vueTsConfigs.recommended,
  {
    // 两份模型由 HTML 顺序加载，保留经典脚本的跨文件全局常量。
    files: [
      "public/games/illusion-prototype/assets/garden-roof-model.js",
      "public/games/illusion-prototype/assets/spire-a-models.js",
    ],
    languageOptions: {
      sourceType: "script",
    },
  },
  {
    rules: {
      "vue/multi-word-component-names": "off",
    },
  },
);
