import pick from '@/materials/base'
import { DEFAULT_CITY, readWeatherCity } from './weather'

export default {
  formData: {
    city: { ...DEFAULT_CITY },
    textColor: '#f8fafc',
    fontFamily: '',
    padding: 14
  },
  formConf(formData: Record<string, unknown>) {
    return {
      city: {
        label: '城市',
        slot: () => <span>{(readWeatherCity(formData.city) ?? DEFAULT_CITY).name}（在卡片内切换）</span>
      },
      ...pick(formData, ['textColor', 'fontFamily', 'padding'])
    }
  }
}
