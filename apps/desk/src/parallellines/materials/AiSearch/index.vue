<template>
  <div
    class="ai-search-wrapper"
    :style="{
      padding: (componentSetting.padding ?? 8) + 'px',
      color: componentSetting.textColor || '#f8fafc'
    }"
  >
    <div class="ai-search-container" :style="{ maxWidth: `${componentSetting.maxWidth || 680}px` }">
      <!-- 一键切换引擎图标栏（AI / 谷歌 / 百度 / Bing / GitHub） -->
      <div class="engine-tabs">
        <button
          v-for="engine in engines"
          :key="engine.id"
          type="button"
          class="engine-tab"
          :class="{ active: activeMode === engine.id }"
          :title="`切换到 ${engine.label}`"
          @click="handleEngineTabClick(engine.id)"
        >
          <span class="engine-dot" :style="{ background: engine.color }">{{ engine.short }}</span>
          <span class="engine-tab-label">{{ engine.label }}</span>
        </button>
      </div>

      <!-- 主搜索 / AI 聊天框 -->
      <div class="search-bar" :class="{ 'is-ai-mode': activeMode === 'ai' }">
        <span class="engine-badge-left" :style="{ background: currentEngine.color }">
          {{ currentEngine.short }}
        </span>

        <input
          ref="inputRef"
          v-model="queryText"
          type="text"
          class="search-input"
          :placeholder="
            activeMode === 'ai'
              ? (followUp ? '继续追问' : '问问 AI')
              : `在 ${currentEngine.label} 中搜索...（按 Tab 切换引擎）`
          "
          @keydown.enter.stop="onSearchEnter"
          @keydown.tab.prevent.stop="cycleEngine"
          @keydown.stop
        >

        <button
          v-if="queryText.trim()"
          type="button"
          class="icon-action-btn"
          title="清空"
          @click="queryText = ''"
        >
          ×
        </button>

        <button
          v-if="queryText.trim() && activeMode === 'ai'"
          type="button"
          class="icon-action-btn"
          title="将当前指令保存为下方快捷图标"
          @click="openAddShortcutWithCurrentQuery"
        >
          ＋
        </button>

        <button
          type="button"
          class="submit-btn"
          :class="{ 'is-ai': activeMode === 'ai' }"
          :disabled="activeMode === 'ai' && aiPending"
          @click="handleSubmit()"
        >
          {{ activeMode === 'ai' ? '问 AI' : `${currentEngine.label}搜` }}
        </button>

        <button
          type="button"
          class="icon-action-btn settings-btn"
          title="搜索与快捷图标设置"
          @click.stop="showSettingsDialog = true"
        >
          ⚙
        </button>
      </div>

      <!-- AI 回答输出面板 -->
      <transition name="ai-fade">
        <div v-if="aiResponseVisible" class="ai-result-card">
          <div class="ai-result-header">
            <div class="ai-result-title">
              <span class="ai-spark">✦</span>
              <span>AI 回答</span>
            </div>
            <div class="ai-result-actions">
              <button v-if="aiPending" type="button" class="mini-btn" @click="stopAi">停止</button>
              <button v-if="aiAnswer && !aiPending" type="button" class="mini-btn" @click="copyAiResult">复制</button>
              <button v-if="aiComplete" type="button" class="mini-btn" @click="startFollowUp">追问</button>
              <a
                class="mini-btn primary"
                :href="chatDeepLink"
                target="_blank"
                rel="noopener noreferrer"
              >
                打开 Chat ↗
              </a>
              <button v-if="!aiPending" type="button" class="mini-btn" @click="aiResponseVisible = false">收起</button>
            </div>
          </div>
          <div v-if="aiAnswer" class="ai-result-body" tabindex="0">{{ aiAnswer }}</div>
          <div v-if="aiStatus" class="ai-result-prompt" role="status">{{ aiStatus }}</div>
        </div>
      </transition>

      <!-- 下方可拖拽、可删除、可设置的快捷图标栏 -->
      <div v-show="!aiResponseVisible" class="shortcut-bar">
        <draggable
          v-model="shortcuts"
          item-key="id"
          class="shortcut-list"
          :animation="180"
          ghost-class="shortcut-ghost"
          @end="persistShortcuts"
        >
          <template #item="{ element: item }">
            <div class="shortcut-chip" :title="item.prompt">
              <button
                type="button"
                class="shortcut-main"
                @click="triggerShortcut(item)"
              >
                <span class="shortcut-icon" :style="{ background: item.color || '#ef4444' }">
                  {{ item.icon || item.name.slice(0, 1) }}
                </span>
                <span class="shortcut-label">{{ item.name }}</span>
              </button>
              <div class="shortcut-ops">
                <button
                  type="button"
                  class="op-btn"
                  title="编辑快捷图标"
                  @click.stop="openEditShortcut(item)"
                >
                  ✎
                </button>
                <button
                  type="button"
                  class="op-btn danger"
                  title="删除快捷图标"
                  @click.stop="removeShortcut(item.id)"
                >
                  ×
                </button>
              </div>
            </div>
          </template>
        </draggable>

        <button
          type="button"
          class="add-shortcut-btn"
          title="新增 AI 快捷图标"
          @click="openAddShortcut"
        >
          ＋ 添加
        </button>
      </div>
    </div>

    <Teleport to="body">
      <dialog ref="aiLoginDialog" class="ai-auth-dialog" aria-label="登录后使用 AI" @close="aiLoginVisible = false">
        <h2>登录后使用 AI</h2>
        <form method="dialog" class="ai-auth-actions">
          <button class="mini-btn">取消</button>
          <button type="button" class="mini-btn" @click="goToAuth(true)">注册</button>
          <button type="button" class="mini-btn primary" autofocus @click="goToAuth(false)">登录</button>
        </form>
      </dialog>
    </Teleport>

    <!-- 快捷图标新增/编辑弹窗 -->
    <easy-dialog
      v-model="shortcutDialogVisible"
      :title="editingShortcutId ? '编辑快捷图标' : '新增快捷图标'"
      width="min(440px, 94vw)"
      height="min(460px, 88vh)"
    >
      <el-form label-position="top" class="shortcut-form">
        <el-form-item label="图标名称">
          <el-input v-model="shortcutForm.name" placeholder="例如：微博热搜" />
        </el-form-item>
        <div class="form-two-col">
          <el-form-item label="图标字符 / Emoji">
            <el-input v-model="shortcutForm.icon" maxlength="2" placeholder="微 / 🔥" />
          </el-form-item>
          <el-form-item label="图标底色">
            <el-color-picker v-model="shortcutForm.color" />
          </el-form-item>
        </div>
        <el-form-item label="点击后发送/填入的 AI 指令">
          <el-input
            v-model="shortcutForm.prompt"
            type="textarea"
            :rows="3"
            placeholder="例如：帮我整理一下最近3小时的微博热搜，按事件热度与核心摘要分点列出"
          />
        </el-form-item>
        <el-form-item label="点击行为">
          <el-radio-group v-model="shortcutForm.autoSend">
            <el-radio :label="true">填入并直接输出 AI 内容</el-radio>
            <el-radio :label="false">仅填入输入框等待补充</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <div style="text-align: right; padding: 10px 12px">
          <button type="button" class="btn" @click="shortcutDialogVisible = false">取消</button>
          <button type="button" class="btn btn-primary" @click="saveShortcutForm">保存</button>
        </div>
      </template>
    </easy-dialog>

    <!-- 搜索栏行为设置弹窗 -->
    <easy-dialog
      v-model="showSettingsDialog"
      title="搜索与 AI 快捷栏设置"
      width="min(440px, 94vw)"
      height="min(280px, 80vh)"
    >
      <div class="settings-panel">
        <div class="setting-row">
          <div>
            <div class="setting-title">搜索后自动添加为快捷入口</div>
            <div class="setting-desc">默认关闭：仅当你手动点击「＋」时才把指令保存到下方图标栏</div>
          </div>
          <el-switch v-model="autoSaveSearchToShortcut" @change="persistSettings" />
        </div>
        <div class="setting-row">
          <div>
            <div class="setting-title">默认交互模式</div>
            <div class="setting-desc">打开页面时输入框默认使用问 AI 或网页搜索</div>
          </div>
          <el-select v-model="defaultMode" style="width: 120px" @change="persistSettings">
            <el-option
              v-for="engine in engines"
              :key="engine.id"
              :label="engine.label"
              :value="engine.id"
            />
          </el-select>
        </div>
      </div>
    </easy-dialog>
  </div>
</template>

<script lang="ts">
import { computed, defineComponent, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import draggable from 'vuedraggable'
import { ElNotification } from 'element-plus'
import { useStore } from '@/store'
import { uid } from '@/utils'
import { getMainAccessToken } from '../../cloudSync'
import { AiSearchError, streamAiAnswer, type AiExchange } from './stream'

export interface AiShortcutItem {
  id: string
  name: string
  icon: string
  color: string
  prompt: string
  autoSend: boolean
}

const DEFAULT_SHORTCUTS: AiShortcutItem[] = [
  {
    id: 'sc-weibo',
    name: '微博热搜',
    icon: '微',
    color: '#e6162d',
    prompt: '帮我整理一下最近3小时的微博热搜，按事件热度与核心摘要分点列出',
    autoSend: true
  },
  {
    id: 'sc-weekly',
    name: '写周报',
    icon: '报',
    color: '#2563eb',
    prompt: '请帮我把以下零碎工作记录整理成结构清晰、重点突出的本周周报：',
    autoSend: false
  },
  {
    id: 'sc-translate',
    name: '精准翻译',
    icon: '译',
    color: '#0d9488',
    prompt: '请将下面内容翻译为自然流畅的中/英文，并保留专业术语准确：',
    autoSend: false
  },
  {
    id: 'sc-explain',
    name: '大白话解释',
    icon: '解',
    color: '#7c3aed',
    prompt: '请用通俗易懂的大白话，分 3 点帮我讲清楚：',
    autoSend: false
  }
]

const ENGINES = [
  { id: 'ai', label: '问 AI', short: '✦', color: '#6366f1', url: '' },
  { id: 'google', label: '谷歌', short: 'G', color: '#ea4335', url: 'https://www.google.com/search?q=' },
  { id: 'baidu', label: '百度', short: '度', color: '#2563eb', url: 'https://www.baidu.com/s?wd=' },
  { id: 'bing', label: 'Bing', short: 'B', color: '#0284c7', url: 'https://cn.bing.com/search?q=' },
  { id: 'github', label: 'GitHub', short: 'GH', color: '#334155', url: 'https://github.com/search?q=' }
]

export default defineComponent({
  name: 'AiSearch',
  components: { draggable },
  props: {
    element: {
      type: Object,
      default: () => ({})
    },
    componentSetting: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const store = useStore()
    const inputRef = ref<HTMLInputElement>()
    const queryText = ref('')
    const showEngineMenu = ref(false)
    const showSettingsDialog = ref(false)

    const defaultMode = ref<string>(props.componentSetting.defaultMode || 'ai')
    const activeMode = ref<string>(defaultMode.value)
    const autoSaveSearchToShortcut = ref<boolean>(
      Boolean(props.componentSetting.autoSaveSearchToShortcut)
    )

    const shortcuts = ref<AiShortcutItem[]>(
      Array.isArray(props.componentSetting.shortcuts) && props.componentSetting.shortcuts.length > 0
        ? JSON.parse(JSON.stringify(props.componentSetting.shortcuts))
        : JSON.parse(JSON.stringify(DEFAULT_SHORTCUTS))
    )

    watch(
      () => props.componentSetting,
      (next) => {
        if (!next) return
        if (Array.isArray(next.shortcuts)) {
          shortcuts.value = JSON.parse(JSON.stringify(next.shortcuts))
        }
        autoSaveSearchToShortcut.value = Boolean(next.autoSaveSearchToShortcut)
        if (next.defaultMode) defaultMode.value = next.defaultMode
      },
      { deep: true }
    )

    const currentEngine = computed(
      () => ENGINES.find((e) => e.id === activeMode.value) || ENGINES[0]
    )

    const aiResponseVisible = ref(false)
    const aiAnswer = ref('')
    const aiStatus = ref('')
    const aiPending = ref(false)
    const aiComplete = ref(false)
    const aiLoginVisible = ref(false)
    const aiLoginDialog = ref<HTMLDialogElement>()
    watch(aiLoginVisible, visible => {
      if (visible && !aiLoginDialog.value?.open) aiLoginDialog.value?.showModal()
      if (!visible && aiLoginDialog.value?.open) aiLoginDialog.value.close()
    })
    const followUp = ref(false)
    const draftKey = 'pl_desk_ai_auth_draft:' + (props.element?.i || '')
    let lastExchange: AiExchange | null = null
    let controller: AbortController | null = null
    let aiToken: string | null = null

    const chatDeepLink = computed(() => 'https://chat.pingxingxian.space/')

    const updateElementSetting = (patch: Record<string, any>) => {
      if (!props.element || !props.element.i) return
      const nextElement = JSON.parse(JSON.stringify(props.element))
      nextElement.componentSetting = {
        ...(nextElement.componentSetting || {}),
        ...patch
      }
      store.editComponent(nextElement)
    }

    const persistShortcuts = () => {
      updateElementSetting({
        shortcuts: JSON.parse(JSON.stringify(shortcuts.value))
      })
    }

    const persistSettings = () => {
      activeMode.value = defaultMode.value
      updateElementSetting({
        autoSaveSearchToShortcut: autoSaveSearchToShortcut.value,
        defaultMode: defaultMode.value
      })
    }

    const selectEngine = (id: string) => {
      activeMode.value = id
      showEngineMenu.value = false
      inputRef.value?.focus()
    }

    const handleEngineTabClick = (id: string) => {
      const hadText = queryText.value.trim().length > 0
      const changed = activeMode.value !== id
      activeMode.value = id
      if (hadText && !changed) {
        handleSubmit()
      } else {
        inputRef.value?.focus()
      }
    }

    const cycleEngine = () => {
      const idx = ENGINES.findIndex((e) => e.id === activeMode.value)
      const next = ENGINES[(idx + 1) % ENGINES.length]
      activeMode.value = next.id
    }

    /** 只在用户点登录或注册时暂存当前问题；不保存答案，也不自动重发。 */
    const goToAuth = (register: boolean) => {
      try {
        sessionStorage.setItem(draftKey, queryText.value)
      } catch {
        ElNotification({ title: '无法保留问题', message: '请先复制问题，再前往登录或注册。', type: 'warning' })
        return
      }
      const params = new URLSearchParams({ redirect: '/desk/' })
      if (register) params.set('mode', 'register')
      window.location.assign('/auth?' + params.toString())
    }

    /** 追问只带最近一次完整回答；关闭页面或变更登录态即丢弃上下文。 */
    const startFollowUp = async () => {
      followUp.value = true
      activeMode.value = 'ai'
      queryText.value = ''
      await nextTick()
      inputRef.value?.focus()
    }

    const stopAi = () => {
      controller?.abort()
      aiStatus.value = '已停止'
    }

    const resetAiSession = () => {
      if (!aiToken || getMainAccessToken() === aiToken) return
      controller?.abort()
      controller = null
      aiToken = null
      lastExchange = null
      aiPending.value = aiComplete.value = followUp.value = aiResponseVisible.value = false
      aiLoginVisible.value = false
      aiAnswer.value = aiStatus.value = queryText.value = ''
    }

    /** 通过主站发起一次付费流，状态提示只针对本次提交，并保留失败草稿。 */
    const runAi = async (prompt: string) => {
      if (controller) return
      resetAiSession()
      queryText.value = prompt
      const token = getMainAccessToken()
      if (!token) {
        aiLoginVisible.value = true
        return
      }
      aiToken = token
      const request = new AbortController()
      controller = request
      const timer = window.setTimeout(() => request.abort(), 115_000)
      const previous = followUp.value ? lastExchange : null
      aiAnswer.value = ''
      aiStatus.value = '正在回答…'
      aiPending.value = true
      aiComplete.value = false
      aiResponseVisible.value = true
      try {
        await streamAiAnswer(token, prompt, previous, request.signal, text => {
          aiAnswer.value += text
          aiStatus.value = ''
        })
        if (!aiAnswer.value.trim()) throw new AiSearchError('workspace_ai_invalid_reply')
        lastExchange = { prompt, answer: aiAnswer.value }
        aiComplete.value = true
        aiStatus.value = ''
        followUp.value = false
      } catch (error) {
        if (controller !== request) return
        if (getMainAccessToken() !== token) {
          resetAiSession()
          return
        }
        const code = error instanceof AiSearchError ? error.code : 'workspace_ai_interrupted'
        if (code === 'workspace_ai_session_invalid') {
          aiResponseVisible.value = false
          aiLoginVisible.value = true
          return
        }
        if (aiStatus.value === '已停止') return
        aiStatus.value = ({
          workspace_ai_insufficient_quota: '请联系管理员开通 AI 额度',
          workspace_ai_account_unbound: '请先绑定 New API 钱包',
          workspace_ai_account_denied: '当前账号无法使用 AI，请联系管理员',
          workspace_ai_model_denied: '当前账号无权使用此模型',
          workspace_ai_rate_limited: '请求过多，请稍后重试',
          workspace_ai_invalid_prompt: '问题或追问上下文不符合要求',
          ai_content_blocked: '内容未通过审核',
          workspace_ai_invalid_reply: '未收到完整回答',
          workspace_ai_unavailable: 'AI 暂不可用',
        } as Record<string, string>)[code] || '回答中断，未自动重试'
      } finally {
        window.clearTimeout(timer)
        if (controller === request) {
          controller = null
          aiPending.value = false
        }
      }
    }

    const handleSubmit = (overridePrompt?: string) => {
      const text = (overridePrompt ?? queryText.value).trim()
      if (!text || (activeMode.value === 'ai' && aiPending.value)) return

      // 仅当用户主动在设置中开启时才自动沉淀为快捷入口（默认关闭）
      if (autoSaveSearchToShortcut.value && activeMode.value === 'ai' && !followUp.value && getMainAccessToken()) {
        const exists = shortcuts.value.some((s) => s.prompt === text)
        if (!exists) {
          shortcuts.value.push({
            id: `sc-${uid()}`,
            name: text.slice(0, 6),
            icon: '✦',
            color: '#6366f1',
            prompt: text,
            autoSend: true
          })
          persistShortcuts()
        }
      }

      if (activeMode.value === 'ai') {
        void runAi(text)
        return
      }

      const target = currentEngine.value
      if (target.url) {
        window.open(`${target.url}${encodeURIComponent(text)}`, '_blank', 'noopener,noreferrer')
      }
    }

    const onSearchEnter = (event: KeyboardEvent) => {
      if (event.isComposing) return
      // 打开登录弹窗时焦点会移到按钮，拦截同一次回车的默认点击。
      event.preventDefault()
      handleSubmit()
    }

    const triggerShortcut = (item: AiShortcutItem) => {
      if (aiPending.value) return
      followUp.value = false
      activeMode.value = 'ai'
      queryText.value = item.prompt
      if (item.autoSend) {
        handleSubmit(item.prompt)
      } else {
        inputRef.value?.focus()
      }
    }

    const shortcutDialogVisible = ref(false)
    const editingShortcutId = ref('')
    const shortcutForm = reactive({
      name: '',
      icon: '✦',
      color: '#6366f1',
      prompt: '',
      autoSend: true
    })

    const openAddShortcut = () => {
      editingShortcutId.value = ''
      shortcutForm.name = ''
      shortcutForm.icon = '✦'
      shortcutForm.color = '#6366f1'
      shortcutForm.prompt = ''
      shortcutForm.autoSend = true
      shortcutDialogVisible.value = true
    }

    const openAddShortcutWithCurrentQuery = () => {
      const text = queryText.value.trim()
      editingShortcutId.value = ''
      shortcutForm.name = text.slice(0, 6)
      shortcutForm.icon = text.slice(0, 1) || '✦'
      shortcutForm.color = '#6366f1'
      shortcutForm.prompt = text
      shortcutForm.autoSend = true
      shortcutDialogVisible.value = true
    }

    const openEditShortcut = (item: AiShortcutItem) => {
      editingShortcutId.value = item.id
      shortcutForm.name = item.name
      shortcutForm.icon = item.icon
      shortcutForm.color = item.color
      shortcutForm.prompt = item.prompt
      shortcutForm.autoSend = item.autoSend
      shortcutDialogVisible.value = true
    }

    const saveShortcutForm = () => {
      const name = shortcutForm.name.trim()
      const prompt = shortcutForm.prompt.trim()
      if (!name || !prompt) {
        ElNotification({ title: '提示', type: 'warning', message: '请填写图标名称与 AI 指令内容' })
        return
      }
      if (editingShortcutId.value) {
        const idx = shortcuts.value.findIndex((s) => s.id === editingShortcutId.value)
        if (idx >= 0) {
          shortcuts.value[idx] = {
            ...shortcuts.value[idx],
            name,
            icon: shortcutForm.icon.trim() || name.slice(0, 1),
            color: shortcutForm.color || '#6366f1',
            prompt,
            autoSend: shortcutForm.autoSend
          }
        }
      } else {
        shortcuts.value.push({
          id: `sc-${uid()}`,
          name,
          icon: shortcutForm.icon.trim() || name.slice(0, 1),
          color: shortcutForm.color || '#6366f1',
          prompt,
          autoSend: shortcutForm.autoSend
        })
      }
      persistShortcuts()
      shortcutDialogVisible.value = false
    }

    const removeShortcut = (id: string) => {
      shortcuts.value = shortcuts.value.filter((s) => s.id !== id)
      persistShortcuts()
    }

    const copyAiResult = async () => {
      try {
        await navigator.clipboard.writeText(aiAnswer.value)
        ElNotification({ title: '已复制', type: 'success', message: 'AI 内容已复制到剪贴板' })
      } catch {
        ElNotification({ title: '复制失败', type: 'error', message: '请检查浏览器剪贴板权限' })
      }
    }

    const closeDropdown = () => {
      showEngineMenu.value = false
    }
    onMounted(() => {
      window.addEventListener('click', closeDropdown)
      window.addEventListener('storage', resetAiSession)
      try {
        const draft = sessionStorage.getItem(draftKey)
        if (draft !== null) {
          sessionStorage.removeItem(draftKey)
          queryText.value = draft
          activeMode.value = 'ai'
          void nextTick(() => inputRef.value?.focus())
        }
      } catch {
        // 禁用会话存储时没有可恢复草稿。
      }
    })
    onUnmounted(() => {
      const request = controller
      controller = null
      request?.abort()
      window.removeEventListener('click', closeDropdown)
      window.removeEventListener('storage', resetAiSession)
    })

    return {
      engines: ENGINES,
      inputRef,
      queryText,
      activeMode,
      defaultMode,
      currentEngine,
      showEngineMenu,
      showSettingsDialog,
      autoSaveSearchToShortcut,
      shortcuts,
      aiResponseVisible,
      aiAnswer,
      aiStatus,
      aiPending,
      aiComplete,
      aiLoginVisible,
      aiLoginDialog,
      followUp,
      goToAuth,
      stopAi,
      startFollowUp,
      chatDeepLink,
      shortcutDialogVisible,
      editingShortcutId,
      shortcutForm,
      selectEngine,
      handleEngineTabClick,
      cycleEngine,
      handleSubmit,
      onSearchEnter,
      triggerShortcut,
      persistShortcuts,
      persistSettings,
      openAddShortcut,
      openAddShortcutWithCurrentQuery,
      openEditShortcut,
      saveShortcutForm,
      removeShortcut,
      copyAiResult
    }
  }
})
</script>

<style lang="scss" scoped>
.ai-search-wrapper {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}

.ai-search-container {
  width: 100%;
  position: relative;
}

.engine-tabs {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
}

.engine-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 11px 0 5px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.13);
  background: rgba(15, 23, 42, 0.32);
  backdrop-filter: blur(14px);
  color: rgba(248, 250, 252, 0.8);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, color 0.16s ease, transform 0.14s ease;

  &:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
    transform: translateY(-1px);
  }

  &.active {
    background: rgba(255, 255, 255, 0.22);
    border-color: rgba(255, 255, 255, 0.38);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
    color: #fff;
    font-weight: 600;
  }
}

.engine-badge-left {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.search-bar {
  position: relative;
  box-sizing: border-box;
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  height: 52px;
  padding: 6px 8px 6px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: blur(22px);
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12), 0 12px 32px rgba(15, 23, 42, 0.28);
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;

  &:focus-within {
    background: rgba(15, 23, 42, 0.56);
    border-color: rgba(96, 165, 250, 0.62);
    box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.18), 0 16px 38px rgba(15, 23, 42, 0.36);
  }
}

.engine-trigger {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 10px 0 6px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  color: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  flex-shrink: 0;

  &:hover {
    background: rgba(255, 255, 255, 0.24);
  }
}

.engine-dot {
  width: 24px;
  height: 24px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.engine-caret {
  font-size: 11px;
  opacity: 0.75;
}

.search-input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: none;
  outline: none;
  background: transparent;
  color: inherit;
  font-size: 15px;

  &::placeholder {
    color: rgba(248, 250, 252, 0.65);
  }
}

.icon-action-btn {
  width: 30px;
  height: 30px;
  border-radius: 999px;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 16px;
  opacity: 0.78;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;

  &:hover {
    opacity: 1;
    background: rgba(255, 255, 255, 0.16);
  }
}

.submit-btn {
  height: 36px;
  padding: 0 16px;
  border: none;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.22);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.18s ease, transform 0.15s ease;

  &.is-ai {
    background: linear-gradient(135deg, #6366f1 0%, #3b82f6 100%);
  }

  &:hover {
    filter: brightness(1.08);
  }
}

.engine-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 8px;
  z-index: 90;
  min-width: 140px;
  padding: 6px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.9);
  backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.16);
  box-shadow: 0 14px 32px rgba(0, 0, 0, 0.35);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.engine-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: #f8fafc;
  font-size: 13px;
  cursor: pointer;
  text-align: left;

  &:hover,
  &.active {
    background: rgba(255, 255, 255, 0.14);
  }
}

.ai-result-card {
  position: relative;
  z-index: 1;
  margin-top: 10px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #172237;
  border: 1px solid rgba(255, 255, 255, 0.18);
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.3);
  text-align: left;
}

.ai-result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  gap: 8px;
  flex-wrap: wrap;
}

.ai-result-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
}

.ai-spark {
  color: #818cf8;
}

.ai-result-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.mini-btn {
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.1);
  color: #f8fafc;
  font-size: 12px;
  text-decoration: none;
  cursor: pointer;

  &.primary {
    background: rgba(59, 130, 246, 0.45);
    border-color: rgba(96, 165, 250, 0.6);
  }

  &:hover {
    background: rgba(255, 255, 255, 0.2);
  }
}

.ai-result-prompt {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.72;
}

.ai-result-body {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.65;
  color: rgba(248, 250, 252, 0.92);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  max-height: min(40vh, 360px);
  overflow: auto;
  overscroll-behavior: contain;
}

.ai-auth-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;

  .mini-btn {
    min-height: 36px;
    padding-inline: 14px;
  }
}

.ai-auth-dialog {
  width: min(380px, calc(100vw - 32px));
  box-sizing: border-box;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 16px;
  background: #172237;
  color: #f8fafc;

  &::backdrop {
    background: rgba(2, 6, 23, 0.58);
  }

  h2 {
    margin: 0 0 18px;
    font-size: 17px;
  }
}

.shortcut-bar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.shortcut-list {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 8px;
}

.shortcut-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(14px);
  border: 1px solid rgba(255, 255, 255, 0.16);
  transition: transform 0.16s ease, background 0.16s ease;
  cursor: grab;

  &:hover {
    background: rgba(255, 255, 255, 0.2);
    transform: translateY(-1px);

    .shortcut-ops {
      opacity: 1;
      pointer-events: auto;
    }
  }
}

.shortcut-ghost {
  opacity: 0.45;
}

.shortcut-main {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px 5px 6px;
  border: none;
  background: transparent;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
}

.shortcut-icon {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
}

.shortcut-label {
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.shortcut-ops {
  position: absolute;
  top: -8px;
  right: -6px;
  display: flex;
  gap: 3px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.15s ease;
}

.op-btn {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: none;
  background: rgba(15, 23, 42, 0.88);
  color: #f8fafc;
  font-size: 11px;
  line-height: 1;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  &.danger:hover {
    background: #ef4444;
  }
}

.add-shortcut-btn {
  height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px dashed rgba(255, 255, 255, 0.3);
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  font-size: 12px;
  opacity: 0.82;
  cursor: pointer;

  &:hover {
    opacity: 1;
    background: rgba(255, 255, 255, 0.14);
  }
}

.shortcut-form {
  padding: 4px 12px 0;
}

.form-two-col {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  align-items: start;
}

.settings-panel {
  padding: 8px 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.setting-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.setting-desc {
  margin-top: 2px;
  font-size: 12px;
  color: #64748b;
}

@media (max-width: 540px) {
  .search-bar {
    height: 46px;
    gap: 5px;
    padding: 4px 6px;
  }

  .engine-badge-left {
    display: none;
  }

  .engine-tab-label {
    display: none;
  }

  .engine-tab {
    padding: 3px;
  }

  .search-input {
    min-width: 0;
    font-size: 14px;
  }

  .submit-btn {
    height: 34px;
    padding: 0 12px;
    font-size: 12px;
  }
}

@media (hover: none), (max-width: 640px) {
  .shortcut-ops {
    opacity: 0.9;
    pointer-events: auto;
  }
}

.ai-fade-enter-active,
.ai-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.ai-fade-enter-from,
.ai-fade-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
