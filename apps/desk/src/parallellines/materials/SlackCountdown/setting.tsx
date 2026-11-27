import pick from '@/materials/base'

export default {
  formData: {
    workStart: '09:00',
    workEnd: '18:00',
    restMode: 'double',
    paydayDay: 15,
    advanceOnRest: true,
    textColor: '#f8fafc',
    fontFamily: '',
    padding: 18
  },
  formConf(formData: any) {
    return {
      workStart: {
        label: '上班时间',
        type: 'input',
        attrs: {
          placeholder: '09:00',
          style: 'width: 140px'
        }
      },
      workEnd: {
        label: '下班时间',
        type: 'input',
        attrs: {
          placeholder: '18:00',
          style: 'width: 140px'
        }
      },
      restMode: {
        label: '休息制度',
        type: 'radio-group',
        radio: {
          list: [
            { name: '双休（周六日）', value: 'double' },
            { name: '单休（仅周日）', value: 'single' }
          ],
          label: 'name',
          value: 'value'
        }
      },
      paydayDay: {
        label: '每月发薪日',
        type: 'input-number',
        attrs: {
          'controls-position': 'right',
          min: 1,
          max: 31,
          style: 'width: 110px'
        },
        unit: '号'
      },
      advanceOnRest: {
        label: '发薪日遇休提前',
        type: 'switch'
      },
      ...pick(formData, ['textColor', 'fontFamily', 'padding'])
    }
  }
}
