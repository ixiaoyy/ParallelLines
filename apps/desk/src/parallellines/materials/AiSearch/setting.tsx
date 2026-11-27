import pick from '@/materials/base'

export default {
  formData: {
    defaultMode: 'ai',
    autoSaveSearchToShortcut: false,
    maxWidth: 680,
    textColor: '#f8fafc',
    padding: 8,
    shortcuts: [
      {
        id: 'sc-polish',
        name: '润色文案',
        icon: '润',
        color: '#e11d48',
        prompt: '请帮我把下面这段文字润色得更清晰自然、表达更有重点，保留原意：',
        autoSend: false
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
  },
  formConf(formData: any) {
    return {
      defaultMode: {
        label: '默认模式',
        type: 'select',
        option: {
          list: [
            { label: '问 AI', value: 'ai' },
            { label: 'Bing', value: 'bing' },
            { label: 'Google', value: 'google' },
            { label: '百度', value: 'baidu' },
            { label: 'GitHub', value: 'github' }
          ],
          label: 'label',
          value: 'value'
        }
      },
      autoSaveSearchToShortcut: {
        label: '搜索后自动添加快捷入口',
        type: 'switch'
      },
      maxWidth: {
        label: '最大宽度',
        type: 'input-number',
        attrs: {
          'controls-position': 'right',
          min: 360,
          max: 1080,
          style: 'width: 110px'
        },
        unit: 'px'
      },
      ...pick(formData, ['textColor', 'padding'])
    }
  }
}
