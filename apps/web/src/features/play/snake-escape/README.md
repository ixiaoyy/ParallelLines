# 蛇蛇出洞

本模块为 ParallelLines 的 Vue 3 / TypeScript / SVG 游戏，无新增生产依赖。

## 开源来源

- 源仓库：[iamrahul25/arrow-escape](https://github.com/iamrahul25/arrow-escape)
- 固定版本：`85167e2c8c2f7273694cf58e0dd333917f2b0c4f`
- `levels.ts` 适配自该版本的 `src/levels/json/level-01.json` 至 `level-50.json`，保留固定种子、蛇路径与参考解。
- `rules.ts` 中的头部通道与碰撞判断适配自 `src/game/geometry.ts`、`src/game/collision.ts`，语义为头部前方射线清空后可离场，身体跟随原路径。
- 原始 MIT 许可及其版权声明原样保留在本目录的 `LICENSE`。该源仓库的许可文件使用 `650 Industries, Inc. (aka Expo)` 版权声明。
- 花园场景、彩蛇 SVG 绘制、网页交互、倒计时与存储实现由本项目制作；未复制抖音游戏图标、画面或其他美术资源。

## 规则与资源边界

50 个内置关卡，棋盘由 8×8 递进至 15×15。关卡数据在构建时打包，运行时不生成候选、不递归搜索、不请求外部服务。可解检查最多消除当前关卡蛇数量次；移除蛇不会新增阻挡，因此任一当前可离场的蛇均可安全移除。

每关三条生命、三次提示、五分钟。撞到其他蛇扣一条生命并保持原布局；耗尽生命或倒计时归零时结束。暂停和页面进入后台均停止计时。重开完全重置当前关卡。下一关只在通关后开放。

进度仅保存最高解锁关卡，使用有版本、校验过的 `localStorage` 记录。浏览器禁用存储时本次会话仍可玩，但刷新后不会保留进度。

## 验证入口

`pnpm --filter @parallellines/web exec playwright test tests/smoke/snake-escape.spec.ts --grep 规则 --workers 1`

该文件的规则用例不启动浏览器、不依赖 API 或数据库，覆盖全部关卡路径合法性与可解性、目标规则、终局与暂停、提示、损坏存储和解锁边界。
