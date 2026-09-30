# 飞翼灌篮

浏览器内单人点按投篮游戏，Vue 3 + TypeScript + Canvas，无新增依赖。

- 点按或空格将竖直速度重置为向上，篮球持续受重力并水平前进。
- 整球从上方进入、从下方离开篮圈才计一次分；反向入圈、漏圈和碰到上下边界结束本局。
- 圈沿碰撞反弹并打断空心连击，干净入圈的连续奖励最高为每圈 5 分。
- 横向速度、圈宽和高度变化有上限；物理以最多 24 个小步处理单帧，逻辑尺寸不随屏幕变化。
- 最高分仅保存在当前浏览器，存储值验证后读取；暂停、重开、隐藏自动暂停与资源释放由界面负责。

## 开源来源及授权

参考并移植了 Mohamed Anis Ben Salah 的
[Flappy-Dunker-Madness](https://github.com/MedAnisBenSalah/Flappy-Dunker-Madness)
中点按复位速度、重力、上下传感器顺序入圈、碰边及漏圈失败、空心连击的规则。
核对版本固定为 `449963736ded7ee804aa312675e3b1d898f4c98d`。
上游 MIT 授权原文保留在本目录 [LICENSE](./LICENSE)。

核对源文件：

- `core/src/com/ormisiclapps/flappydunkermadness/game/entities/physical/Player.java`
- `core/src/com/ormisiclapps/flappydunkermadness/game/core/GameIntelligence.java`
- `core/src/com/ormisiclapps/flappydunkermadness/game/core/GameLogic.java`
- `core/src/com/ormisiclapps/flappydunkermadness/game/world/GameWorld.java`

本版本将玩法重写为独立 TypeScript 规则，调整为固定逻辑尺寸、持续轨迹检查、受限难度与有界连击。
不包含上游 LibGDX/Box2D、广告 SDK、联网排行榜、商店、复活广告和第三方素材。
篮球、翅膀、篮圈、背景均由本项目 Canvas 自绘。

## 本地验证

规则测试独立于浏览器和 API：

```powershell
pnpm --filter @parallellines/web exec playwright test tests/smoke/flappy-dunk.spec.ts
```

真实入口为 `/play/flappy-dunk`。浏览器验收还应检查手机点按、空格、圈沿弹开、暂停继续、重开、隐藏后恢复、旋转屏幕和最高分保留。
