import pick from '@/materials/base'

const defaultTarget = new Date(Date.now() + 7 * 86400 * 1000)
const pad2 = (n: number) => String(n).padStart(2, '0')
const toLocalIso = (d: Date) =>
  `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}T${pad2(d.getHours())}:${pad2(d.getMinutes())}`

export default {
  formData: {
    eventName: '重要目标',
    targetTime: toLocalIso(defaultTarget),
    startTime: toLocalIso(new Date()),
    style: 'flip',
    accentColor: '#60a5fa',
    textColor: '#f8fafc',
    fontFamily: '',
    padding: 18,
  },
  formConf(formData: any) {
    return {
      eventName: {
        label: '事件名称',
        type: 'input',
        attrs: {
          placeholder: '例如：版本上线 / 考研 / 纪念日',
        },
      },
      targetTime: {
        label: '目标时间（YYYY-MM-DDTHH:mm）',
        type: 'input',
        attrs: {
          placeholder: '2026-12-31T18:00',
        },
      },
      startTime: {
        label: '起始时间（用于进度条/圆环）',
        type: 'input',
        attrs: {
          placeholder: '2026-11-27T09:00',
        },
      },
      style: {
        label: '倒计时样式',
        type: 'select',
        option: {
          list: [
            { label: '翻页卡片', value: 'flip' },
            { label: '极简大字', value: 'minimal' },
            { label: '进度条', value: 'progress' },
            { label: '环形仪表', value: 'ring' },
          ],
          label: 'label',
          value: 'value',
        },
      },
      accentColor: {
        label: '强调色',
        slot: () => <standard-color-picker vModel={formData.accentColor} />,
      },
      ...pick(formData, ['textColor', 'fontFamily', 'padding']),
    }
  },
}
