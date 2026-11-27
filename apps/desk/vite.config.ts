import { defineConfig } from 'vite'
import { resolve } from 'path'
import Vue from '@vitejs/plugin-vue'
import VueJSX from '@vitejs/plugin-vue-jsx'
import { plugin as VueMarkdown, Mode } from 'vite-plugin-markdown';
import VueI18n from '@intlify/unplugin-vue-i18n/vite'
// import { visualizer } from 'rollup-plugin-visualizer'

const base = process.env.VITE_DESK_BASE || '/'

// https://vitejs.dev/config/
export default defineConfig({
  base,
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      'vue-i18n': 'vue-i18n/dist/vue-i18n.runtime.esm-bundler.js'
    }
  },
  optimizeDeps: {
    include: [
      'vue',
      'vue-i18n',
      'pinia',
      'pinia-plugin-persistedstate',
      'vue-grid-layout',
      'element-plus',
      'vuedraggable',
      '@howdyjs/to-control',
      '@howdyjs/mouse-menu',
      'dayjs'
    ]
  },
  css: {
    preprocessorOptions: {
      scss: {
        charset: false,
        additionalData: '@use "@/assets/element-variables" as *;'
        // additionalData: "@import '@/assets/variables.scss';"
      }
    }
  },
  plugins: [
    Vue({ include: [/\.vue$/] }),
    VueJSX(),
    VueMarkdown({
      mode: [Mode.HTML, Mode.TOC, Mode.VUE]
    }),
    VueI18n({ include: resolve(__dirname, 'src/lang/locales/**') })
    // visualizer()
  ],
  build: {
    outDir: 'dist-desk'
  },
  server: {
    host: '127.0.0.1',
    port: 5222
  }
})
