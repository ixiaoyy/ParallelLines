# 2026-11-03 外链 Web 游戏收录批次

## 范围与入口

本批代码与 `0102` 数据迁移已通过既有发布流水线部署，四张正式封面已先行上传到生产静态资源存储。
用户于 2026-11-03 授权直接上线并停止追加校验；未另做生产目录、数据回读或浏览器验收。
四款均从此前参考站 `gd.games` 选择，使用现有 `external` 类型和 HTTPS 作品页；
点击目录卡片后在新标签页前往原站，不在本站嵌入或托管游戏包，也不标记为 AI 生成。

数据链路不变：`catalog_projects` → 公开目录 API → 游戏卡片 → 原站链接。
封面链路不变：后台自定义封面优先，否则以稳定 `slug` 读取 `coverManifest.ts`，再解析到静态资源域名。
本批不修改目录服务、页面布局、已有游戏、评分或浏览量。

## 游戏与作者来源

| 标识 | 分类 | 游戏与游玩入口 | 作者署名 | 作者链接及说明 |
| --- | --- | --- | --- | --- |
| `gd-spectrum` | `puzzle` / 解谜 | [Spectrum](https://gd.games/mrmeeseeks/spectrum) | Calastrovsk | [原站作者主页](https://gd.games/Calastrovsk)；入口路径仍含旧名称 `mrmeeseeks`，不据路径推断署名。 |
| `gd-fungi-run` | `stages` / 闯关 | [Fungi Run](https://gd.games/shehan/fungirun) | SHEHAN | [原站作者主页](https://gd.games/SHEHAN)。 |
| `gd-super-chicken-td` | `tower-defense` / 塔防 | [Super Chicken TD](https://gd.games/texugozap/super-chicken-td) | texugozap / Rafa38gh | 作者链接使用列出两位作者的作品页；正文另署创作名 Texugo 与 TemptyOne，保留平台公开账号，不漏合作者。 |
| `gd-golf-adventures-2` | `casual` / 休闲 | [Golf Adventures! 2](https://gd.games/zachjukamashi/golf-adventures-2) | ZachjuKamashi / lhphr | 作者链接使用完整署名的作品页；沿用已有休闲分类，不为迷你高尔夫新增分类。 |

简介只采用原站已确认玩法：Spectrum 同步控制三个颜色角色解谜；Fungi Run 包含二段跳、冲刺和射击；
Super Chicken TD 用小鸡保护庄稼；Golf Adventures! 2 包含 108 关与 5 种主题，并保留首次加载较慢的提示。
合作作品沿用现有单个 `author_url` 字段，指向可看到完整署名的作品页，不增加字段或把作者错误链接到某一位合作者。

## 正式封面来源与处理

封面均来自作品原站或作者自己的作品页，不使用分类色块、默认占位图或生成的假游戏画面。
仅转换编码，保留原始构图与分辨率；Spectrum 从作者公开实机动画提取一帧。
原图及检查记录留存在本次任务可视化目录，不作为生产资源发布。

| 标识 | 图片来源 | 最终尺寸 | WebP 字节 | 处理 |
| --- | --- | --- | ---: | --- |
| `gd-spectrum` | [作者官方作品页](https://calastrovsk.itch.io/spectrum)中的 [Level 1 实机 GIF](https://img.itch.zone/aW1hZ2UvMTkxMTE2MS8xMTIzODE0OS5naWY=/original/ijneNi.gif) | 320 × 180 | 30,802 | 第 32 帧，无损 WebP；原始低分辨率像素图，不放大、不宣称高清。 |
| `gd-fungi-run` | [原站分享封面](https://games.gdevelop-app.com/game-ba20caed-f784-4089-9ea0-4469ef3321fe/g89052.jpg) | 1920 × 1080 | 116,794 | WebP quality 90，不缩放、不裁切。 |
| `gd-super-chicken-td` | [原站分享封面](https://games.gdevelop-app.com/game-1444919f-f147-4ac4-b31f-3e152bf377f4/liluo.png) | 1920 × 1080 | 190,258 | 无损 WebP。 |
| `gd-golf-adventures-2` | [原站分享封面](https://games.gdevelop-app.com/game-f1d1d5ae-fa28-4725-ac05-c2adbed4d485/GDgamesCover.png) | 1920 × 1080 | 6,518 | 无损 WebP。 |

Spectrum 的 `og:image` 及 `screenshotUrls` 图片经实际查看均为标题菜单，因此没有采用；
作者 itch.io 页面明确链接本批 gd.games 同一作品，实机动画可以确认归属。
Level 4 动画帧在目录居中裁切后丢失右侧角色，最终改用 Level 1 角色与颜色分离机关居中的第 32 帧。
其他三张原站图片返回通用 `application/octet-stream`，已实际解码确认为 PNG/JPEG 后转换；
发布目标必须按 `.webp` 返回图片类型，不能仅凭扩展名验收。
本清单记录公开宣传图的出处，不代表取得游戏包或素材再分发许可；本批不下载、分发游戏包。

## 文件与发布清单

生产文件必须作为同一批次交付：

- `apps/api/alembic/versions/0102_add_selected_web_games.py`
- `apps/web/src/features/catalog/coverManifest.ts` 中本批四个映射
- 下表四张正式图片
- 本来源与发布清单 `static/web/catalog/2026-11-03-v1/README.md`，随本批素材保留；本地 `docs/` 受忽略规则排除，因此清单放在实际素材目录。

本地图片目录：`static/web/catalog/2026-11-03-v1/covers/`。
生产资源目标如下；本批已实际上传，按用户要求未再做回读、公开地址或浏览器校验。

| 本地文件 | 公开目标地址 |
| --- | --- |
| `gd-spectrum.webp` | `https://img.pingxingxian.space/static/web/catalog/2026-11-03-v1/covers/gd-spectrum.webp` |
| `gd-fungi-run.webp` | `https://img.pingxingxian.space/static/web/catalog/2026-11-03-v1/covers/gd-fungi-run.webp` |
| `gd-super-chicken-td.webp` | `https://img.pingxingxian.space/static/web/catalog/2026-11-03-v1/covers/gd-super-chicken-td.webp` |
| `gd-golf-adventures-2.webp` | `https://img.pingxingxian.space/static/web/catalog/2026-11-03-v1/covers/gd-golf-adventures-2.webp` |

新增一份数据迁移，版本 `0102_add_selected_web_games`，前置 `0101_catalog_ai_ratings`，不改表结构。
迁移先核齐所需四个分类，再按固定标识或有无末尾斜线的入口地址去重；隐藏、跨分类的已有条目也保留。
排序从包含隐藏条目的分类末尾追加，不创建评分、不修改旧统计。
幂等只针对上述固定标识与地址等价形式；不承诺识别管理员另加的跟踪参数或平台地区路径。

本次已获直接上线授权，发布顺序为（用户另要求停止追加校验，未执行下列验收项）：

1. 内容负责人确认宣传素材展示用途与来源，发布人员核对真实目录，避免遗漏管理员后来维护的内容。
2. 先上传本批四张正式图片，逐项核对 `200`、`image/webp` 和浏览器可解码尺寸。
3. 再发布目录迁移与前端映射；不假定现有 Web 构建或 CI 会自动上传 `static/web`。
4. 在真实目录中逐款核对封面实际地址、加载、裁切、作者和外链目标，保存截图后才可宣布上线完成。

回退沿用既有收录约定：`downgrade()` 不删除业务记录或评分；撤下单款使用管理员隐藏入口。
如需回退前端，不应删除旧版本静态文件，以便恢复原映射；所有目标环境操作仍须单独授权。

## 验证入口与证据边界

- Python 回归：`apps/api/tests/test_catalog_selected_web_games_migration.py`，独立内存 SQLite，
  验证准确资料、防重、隐藏/跨分类记录保留、分类缺失前置终止、排序、统计与非删除回退。
- Web 回归：`apps/web/tests/smoke/selected-web-games-catalog.spec.ts`，固定 API 响应和本地正式图片，
  检查桌面/手机网格与列表、作者、图片实际解码及裁切、外链新标签和打开统计。
- 上述夹具不能证明项目数据库、线上 CDN 或外站游戏当前可玩；外链弹窗使用本地响应，不向原站发送测试统计。
- 四张生产图片已实际上传；目录数据与前端发布状态随后记录，未执行追加回读或线上目录验收。

### 本次本地结果

| 检查 | 实际结果 |
| --- | --- |
| Python 定向迁移回归 | 19 passed；内存 SQLite。96 条 SQLite 默认 datetime adapter 弃用警告，无用例失败。 |
| 新迁移与 Python 测试语法 | `py_compile` 通过。 |
| Web 类型检查 | `pnpm typecheck:web` 通过。 |
| 最终 Web smoke | 2 passed；桌面 1280 × 900、手机视口 390 × 844。使用最终图片及与迁移相同的精确外链地址。 |
| 人工查看最终截图 | 已查看两端网格和列表；四图均实际加载，Fungi 蘑菇、Chicken 标识、Golf 球场可识别。Spectrum 最终中心角色与机关保留，网格渐变下偏暗，原始像素图清晰度有限。 |

独立回归命令（前两条在 `apps/api` 执行；不使用 `pnpm test:api`）：

```powershell
& '.\.venv\Scripts\python.exe' -m pytest --noconftest -q tests/test_catalog_selected_web_games_migration.py
& '.\.venv\Scripts\python.exe' -m py_compile alembic/versions/0102_add_selected_web_games.py tests/test_catalog_selected_web_games_migration.py
```

项目根目录执行：

```powershell
pnpm typecheck:web
# 先在独立的本地 Vite 端口提供页面，再只跑本批 smoke；API 与外链均被本地夹具响应。
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:5191'
pnpm --dir apps/web exec playwright test tests/smoke/selected-web-games-catalog.spec.ts --workers=1 --reporter=list
```

本次临时 Vite 5191 已停止，不保留后台服务。
最终截图位于 `C:/Users/phpxi/.codex/visualizations/2026/11/03/01a1a092-c3dc-7f13-96a1-dfece97ebb8a/selected-web-games/qa/`：
`selected-web-games-grid-desktop.png`、`selected-web-games-grid-mobile.png`、
`selected-web-games-list-desktop.png`、`selected-web-games-list-mobile.png`。

### 真实外站的未完成验收

四款原站作品页读取成功，作者与素材来源已核对。Spectrum 在浏览器中已加载标题菜单及游戏画布，
但进入游玩时遇到跨框架坐标检查失败和浏览器操作超时；不能据此宣称已试玩通过。
其余三款也未完成真实浏览器逐款试玩。用户明确要求停止追加校验并直接发布，本批保留该证据限制，
不把未试玩写成通过，也不再以追加试玩或页面验收作为本次发布前置条件。

## 发布基线适配

线上主线已存在 `0101_catalog_ai_ratings`，本批改为 `0102_add_selected_web_games` 并接在该版本之后，避免形成两个迁移头；四款数据与迁移逻辑不变。原目录已回到 `main`，实际发布只从原目录进行。既有 19 项回归、2 项 Web 检查和类型检查属于原本地候选证据；用户要求停止校验后未重跑。原旧分支的 0101 候选已随原改动保存在命名 stash 中，不得作为额外迁移再次发布。

静态图片发布入口 `apps/api/scripts/upload_static_web_assets.py` 已补齐四个本批 key；实际上传未使用 `--verify` 或 `--dry-run`，未手动运行额外测试、lint、类型检查或浏览器验收；既有发布流水线保持原样。

### 最终发布与目录整理结果

- 四张封面已实际上传到本清单的生产静态地址，仅采信上传命令成功，未追加回读或浏览器校验。
- 原目录 `D:/work/pingx/ParallelLines` 已恢复为 `main`，接入性能发布负责人的 `75a229ef` 镜像身份兼容修复后，通过本机既有 Git/SSH 通道提交推送本批，不修改连接权限或凭据。
- 最终游戏提交为 `291534d39a9113c17979ed85dba9c6b5ba6f7d9b`；首次 `49259d1e` 因本批测试文件的 E501、B905 两处格式规则失败，未进入部署，修正后继续同批前后端发布。游戏资料和业务逻辑没有因此调整。
- [CI 41617898084](https://github.com/ixiaoyy/ParallelLines/actions/runs/41617898084) 与 [Deploy 41618727101](https://github.com/ixiaoyy/ParallelLines/actions/runs/41618727101) 均成功；后端 `api + worker`、前端 `web` 实际部署步骤成功，full-stack 与 Nginx 独立任务跳过。没有用旧失败运行冒充成功。
- 后续主线接入 `624789cde2d3f4a43d744d0e16be0f275e857d95`，只持久化现有网关 Chat/API 网络声明，完整保留游戏提交；该项由原性能任务负责人完成，未修改本批游戏。
- 原先 GitHub 连接返回的 `403 Resource not accessible by integration` 仅属于该连接的写入拒绝，本机既有 Git/SSH 提交推送已实际成功，不能将二者混为同一个权限结论。
- 原目录先前的暂存、未暂存和未跟踪改动保存在 stash `8cd23b816d5ce7b9ff9ec7877c80474ee81072d6`；补丁与恢复记录位于 `.tmp/main-consolidation-20261103/`。未混入本批提交。
- 游戏与性能临时目录均已整体移入 `.tmp/retained-release-workspaces/20261103/` 下的 `web-games/`、`performance/`，保留完整 `.git`、依赖及产物，原上层临时入口已移除，没有永久删除内容。
- 用户要求停止追加校验后，没有手动重跑测试、类型检查、lint 或页面验收；现有发布流水线自带的 CI 和镜像完整性步骤保持不变。发布任务成功不等于已逐款验证生产数据或实际页面。

