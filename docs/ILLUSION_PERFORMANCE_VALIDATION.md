# 第四关渲染性能：发布基线与验收边界

## 版本与范围

本轮从真实 `main` 提交 `9c4318d2b9cafc4574e8d1b8558ffb6214f4e94e` 移植性能差异。
该版本第四关包含鞋/袍采样、门面命中、`drawWorld(false)` 和低帧子步等既有修复。
没有用旧工作区整份 HTML 覆盖它们。

生产改动仅在 `apps/web/public/games/illusion-prototype/level4.html`：

- 固定水院、荷叶、小亭和倒影复用原有实例；不缓存全部 `static`，不缓存可动机关或行走支撑。
- 每种几何复用 CPU/GPU 实例缓冲，按当前帧首次出现的种类顺序绘制；实际 Float32 数据变化才上传。
- 保留负零与原颜色编码、遮挡、透明绘制顺序。

跨帧 DOM 位置缓存已撤回。相机、取景、CSS、拓扑、采样、机关、输入、剧情、终点和重开均未修改。
已将两个性能区以外的关卡源码与此 `main` 基线逐段比对，保持相同。

## 本轮新证据

| 层级 | 实际检查 | 结论与限制 |
| --- | --- | --- |
| 冻结 WebGL 场景 | 开场、A 旋转、B 区、C 旋转、室内、终台、完成和重开，共 8 种状态 | 原版与候选的画布像素、实际 GPU 实例、对象/支撑资料、投影相同，WebGL 错误码为 0；没有采集新 CPU 基准。 |
| 真实入口 | 在支持核对 URL 的 Chrome 标签中，操作原有阶梯/A 件、点按实际道路并上阶，随后重开 | 角色到达中央道路，路线清空，无失败状态；原按钮恢复角色和机关。没有直接写入入口玩法状态。 |
| 近终点受控 fixture | 建立前置条件及偏心脚点 `[22.53,10.8,-1.7]`；用原 `checkProgress` 建立归中意图 | 为稳定检查输入门禁，fixture 明确暂停生命周期恢复；真实键盘和目标道路点击不改写归中意图。此阶段不是连续行走验收。 |
| 恢复原循环 | 点击 fixture 的恢复按钮，恢复原 `resume`/`pageshow`，由原 rAF 和关卡逻辑继续 | 到达 `[22.2,10.8,-1.7]` 后完成；出现原结束文字/下一关入口，完成后输入仍锁定，原按钮重开后机关输入恢复。没有直接设置获胜状态。 |

本地结果位于 `.tmp/performance-main-baseline-20261103/`：

- `level4-before.json`、`level4-after.json`、`level4-equivalence-summary.json`：新发布基线的冻结对照。
- `level4-real-walk.json`、`level4-real-walk.jpg`：真实入口路线记录。
- `level4-goal-smoke.json`、`level4-goal.jpg`：受控终点门禁与完成记录。

真实截图已查看。记录不会把 mock API、受控状态或截图称作真人完整通关。
实际平板、连续流畅度和完整当前版本试玩仍未签验收；既有约一秒 rAF 调度异常不在本批修复范围。
不重开已搁置的墙闪问题。

## 复现冻结对照与局部烟测

仅在明确的本地验收阶段运行。脚本只绑定回环地址，不启动浏览器、不访问生产 API、不读取凭证。
必须在 Git 中已有上述固定基线；缺失时直接报错，不回退到其他版本。

```powershell
node docs/illusion-validation/local-qa.cjs
```

在受支持且能可靠核对当前 URL 的浏览器会话中，依次打开：

1. `http://127.0.0.1:5197/games/illusion-prototype/level4.html?qa=equivalence&variant=before`
2. `http://127.0.0.1:5197/games/illusion-prototype/level4.html?qa=equivalence&variant=after`

两页分别显示等价采集完成后，运行：

```powershell
python docs/illusion-validation/compare-results.py
```

真实入口使用 `?qa=smoke&variant=after`；近终点受控状态使用 `?qa=goal&variant=after`。
只有后者含显式测试状态和暂停/恢复控制，不用于代签完整流程。
操作结束关闭本人创建的标签和临时服务，不关闭其他窗口或服务。

该 fixture 同时提供隔离目录数据，供目录 Card 接线检查使用。需启动本地 Web 时，仅在该进程设置
`VITE_API_BASE_URL=/api/v1`、`VITE_STATIC_ASSET_BASE_URL=/`、
`VITE_DEV_API_PROXY_TARGET=http://127.0.0.1:5197`。不要把这些验收参数带入正式构建。

## 历史证据不能换名沿用

旧工作区 `d3df0c6a…` 到 `da07f092…` 的 CPU、分配和上传测量属于旧基线。
旧原型缺少真实 `main` 的部分姿态/门/子步修复，不能将旧 CPU 数字称作此发布组合的结果。
相同 PNG 输入的无损转码证据、内容未变的工具测试可以按对应源文件继承，
但整景帧率、真实设备体验和新组合行为须分别列明。本轮没有为凑提速数字再跑性能基准。
