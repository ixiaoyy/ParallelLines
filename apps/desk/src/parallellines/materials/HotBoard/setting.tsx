export default {
  formData: {
    defaultSource: 'weibo',
    maxItems: 10,
    showRankBadge: true,
    textColor: '#f8fafc',
    fontFamily: '',
    padding: 16,
  },
  formConf() {
    return {
      defaultSource: {
        label: '默认榜单',
        type: 'select',
        option: {
          list: [
            { label: '微博热搜', value: 'weibo' },
            { label: '百度热搜', value: 'baidu' },
            { label: 'B站热门', value: 'bilibili' },
            { label: 'Hacker News', value: 'hackernews' },
          ],
          label: 'label',
          value: 'value',
        },
      },
      maxItems: {
        label: '展示条数',
        type: 'input-number',
        attrs: { min: 3, max: 20, step: 1 },
      },
      showRankBadge: {
        label: '显示排名序号',
        type: 'switch',
      },
      textColor: {
        label: '文字颜色',
        type: 'color-picker',
      },
      padding: {
        label: '内边距',
        type: 'input-number',
        attrs: { min: 0, max: 36, step: 2 },
      },
    }
  },
}
