import pick from '@/materials/base'

export default {
  formData: {
    alarms: [],
    systemNotifications: false,
    textColor: '#f8fafc',
    fontFamily: ''
  },
  formConf(formData: Record<string, unknown>) {
    // 闹钟和权限由卡片内的专用控件维护，设置面板只提供外观设置。
    return pick(formData, ['textColor', 'fontFamily'])
  }
}
