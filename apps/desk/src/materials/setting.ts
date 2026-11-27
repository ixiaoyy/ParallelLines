import Empty from './Empty/setting'
import Clock from './Clock/setting'
import Search from './Search/setting'
import Collection from './Collection/setting'
import TodoList from './TodoList/setting'
import CountDown from './CountDown/setting'
import Day from './Day/setting'
import Editor from './Editor/setting'
import Bookmark from './Bookmark/setting'
import SlackCountdown from '@/parallellines/materials/SlackCountdown/setting'
import AiSearch from '@/parallellines/materials/AiSearch/setting'
import WeatherCard from '@/parallellines/materials/WeatherCard/setting'
import AlarmTimer from '@/parallellines/materials/AlarmTimer/setting'

const Setting: Record<string, ComponentSetting> = {
  Empty,
  Clock,
  SlackCountdown,
  AiSearch,
  WeatherCard,
  AlarmTimer,
  Search,
  Collection,
  TodoList,
  CountDown,
  Day,
  Editor,
  Bookmark,
}

export default Setting
