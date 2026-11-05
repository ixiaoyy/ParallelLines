# 2026-11-05 单游戏直站收录批次

## 已确认范围与入口

用户已确认本批三款、正式封面、验证后只提交推送本批到 `main`，并按原流程上传部署。
继续使用 `external`：目录 API → 单款游戏卡片 → 新标签直达游戏本体。
游戏自己的开始菜单、教程、Steam 推广链接不等同聚合平台落地页；不把作者官网或作品介绍页当游玩入口。
本批不改旧项目和统计，不重新展示此前九款隐藏记录，不标记为 AI 生成，不托管游戏包。

| slug | 名称 / 分类 | 直达地址 | 作者与主页 |
| --- | --- | --- | --- |
| `yorg-io` | YORG.io / `tower-defense` 塔防 | [YORG.io](https://yorg.io/) | Tobias Springer / tobspr Games；[官方主页](https://tobspr.io/) |
| `shapez-demo` | shapez（网页试玩版） / `simulation` 模拟经营 | [shapez Demo](https://shapez.io/) | 同一完整署名与主页，作者榜聚合为两作品，不拆成两个作者 |
| `ztype` | ZType / `shooting` 射击 | [ZType](https://zty.pe/) | Dominic Szablewski / PhobosLab；[作者主页](https://phoboslab.org/) |

YORG 原站 HTML `author` 为 Tobias Springer，工作室官网明确列出 YORG.io（2018）和 shapez（2020），
并说明工作室由 Tobias Springer 创立；不混入 YORG.io 3 或 shapez 2。
[shapez 官方仓库](https://github.com/tobspr-games/shapez.io)明确将该地址列为 Online Demo；
网页试玩与付费完整版分开，不将完整版额外关卡、设施、电线模式等写成免费试玩能力。
ZType 的来源为[作者发布文章](https://phoboslab.org/log/2011/01/z-type)及正式作品集，操作描述限英文键盘打字。

## 正式封面与处理

本地文件在本目录 `covers/`，正式目标前缀为
`https://img.pingxingxian.space/static/web/catalog/2026-11-05-v3/covers/`。
三图最终共 **376,700 字节**，已逐张实看，不使用纯标题、结算或加载截图作封面。

| 文件 | 来源与画面 | 原始文件 | 最终文件 |
| --- | --- | --- | --- |
| `yorg-io.webp` | [原版官方 Press Kit](https://yorg.io/press.html) 的[基地防线宣传图](https://yorg.io/assets/press/banner.png)，非 YORG.io 3 | PNG 1919×662，351,199 B | 1280×442，240,268 B；等比例缩小后无损 WebP，完整构图 |
| `shapez-demo.webp` | 当前匿名网页版正常放置开采器并拖拽运输线的实机，仅第一关试玩路线 | 全图 PNG 1280×900，211,089 B；选取矩形 PNG 990×800，122,180 B | 990×800，74,940 B；无损 WebP，不放大或补画 |
| `ztype.jpg` | [作者作品集](https://phoboslab.org/games)的[真实射击图](https://phoboslab.org/content/assets/ztype.jpg)，含玩家飞船、敌词、激光及爆炸 | JPEG 560×372，61,492 B | 原 JPEG 原字节，560×372，61,492 B |

shapez 的矩形取自原截图 `[x=290,y=0,width=990,height=800]`，排除左侧教学面板和底部工具栏，
保留中心、路线、真实试玩标识和传送带说明。不将中心 `0/10` 当作成功交付或通关。
更紧的 740×500 候选截断中心建筑顶部，已舍弃。

ZType 完整原图转无损 WebP 为 99,594 B，反而更大，因此保留 JPEG；不为统一扩展名重复有损编码。
本次正常开局截图未验证打字命中，正式封面采用作者实机图，不把结算或输入失败冒充成功射击。
仓库优化脚本对两张 WebP 检查无更小像素等价结果，保持文件；脚本仅支持 PNG / WebP，不拿它伪装完成 JPEG 检查。
上传构造器只补 `.jpg → image/jpeg` 分支，既有 SVG / WebP 类型逐项静态校验保持不变。

初轮测试虽通过，实际窄横卡把 ZType 靠底的玩家飞船裁掉；最终仅对这张精确版本图片设置
`object-position:center bottom`。其他封面、后台自定义图片、布局与默认定位不变。
最终两端推荐 / 分类卡中飞船、敌词及激光均保留。shapez 横卡会裁掉图内顶部试玩字样，
但图片确为试玩初关且名称明确标注网页试玩，中心和运输线可辨，不另加假字或替换付费版画面。

原图、来源、缩放 / 裁切、编码和排除记录位于本次可视化 `native-direct-games-release/assets/delivery.json`。
YORG Press Kit 明确提供图片用于介绍 / 缩略图；其他出处在上表保留。来源记录不代表取得游戏包或其他素材再分发许可。

## 同批交付与迁移语义

- `apps/api/alembic/versions/0106_add_direct_game_sites.py`：唯一数据迁移，前置 `0105_catalog_direct_entries`，无 DDL。
- `apps/web/src/features/catalog/coverManifest.ts`、`coverAspectManifest.ts`：实际文件名 / 扩展名 / 真实宽高比。
- `apps/web/src/pages/catalog/CatalogGameCard.scss`：仅上述 ZType 精确源的底部定位，不是全局布局变化。
- `apps/api/scripts/upload_static_web_assets.py`：三张 v3 静态 key 和 JPEG 类型。
- 三张正式图片、本清单，以及本批 API 独立 / Web 两端回归。

先核齐三个分类，再以固定 slug 或入口有无末尾斜线防重，包含隐藏 / 跨分类记录；
不覆盖旧人工资料 / 隐藏状态 / 统计，追加到包含隐藏项的分类末尾，浏览量默认零，不创建评分。
幂等不额外识别跟踪参数等其他等价入口，复用现有收录合同。

先限定 `--catalog-only --catalog-version 2026-11-05-v3 --verify` 上传三图，公开 `200` 且图片类型 / 解码正确后，
再发布迁移与前端引用。JPG 必须为 `image/jpeg`，两张 WebP 为 `image/webp`，不能只凭上传成功验收。
上线后逐款真实电脑 / 手机目录核查 href、作者 / 合作别名、图片实际 src / 自然尺寸 / 裁切和此前九款仍隐藏。

本批三对象上传前均确认为不存在的新对象，实际限定版本上传及存储回读通过；公开 GET 为
`200 image/webp`、`200 image/webp`、`200 image/jpeg`，均与本地字节一致且可解码。
没有覆盖旧对象、重传其他版本或清全局缓存。

## 已做检查与恢复准备

- 独立内存 SQLite 回归 **16 passed**；语法、定向 Ruff / 空白检查通过，非真实 MySQL 验收。
- Web 初轮 2 passed 后发现实际 ZType 裁切缺陷，修正后最终两端 **2 passed**；
  新图与旧蛇蛇定位回归、发现页分页、分类 / 搜索、精确 URL / 本地弹窗统计、试玩名称、共享作者和别名搜索通过。
  Vite 5195 已停止。根代理已查看最终 YORG 与 ZType 两端分类 / 推荐截图及 shapez 内容。
- `pnpm typecheck:web`、上传脚本语法 / Ruff 和新旧资产 MIME 接线通过；
  此后 TypeScript 输入未变，最终 Sass 定位由实际 Vite 渲染及两端回归覆盖，不重复无关检查。
- 真实生产初查 schema 为 `0105`，新三个分类齐全，候选标识 / URL 包含隐藏去重没有已有记录。
  之前十二条和评分原值已留快照：公开 227、九款仍隐藏，Canteen 浏览 6 / Dungeon 浏览 1 / 其余 0。
- 恢复目录：`/data/releases/direct-game-sites-20261105-01a1a966/`，旧 API / worker / Web 标签及独立恢复 shell 已准备。
  前后旧记录保留、生产新增资料与页面验收将另记；本地证据不冒充生产生效。

`downgrade()` 不删除项目或评分。服务回退使用已保存镜像，旧 API 跳过迁移启动以免不识别 `0106`；
若一并回退旧 Web，需要管理员先处理新三条可见性以免缺少旧版封面映射，脚本不自动删 / 改业务数据。
不清上传 / 备份卷，不清全局缓存或删除旧静态文件。

## 外站核验边界

匿名浏览器实际进入 YORG 中文互动教程且按钮响应；shapez 进入第一关，封面阶段正常建了初始路线；
ZType 实际开局至第一波 / 结算，但没有成功命中验证。未测外站手机玩法或完整通关，不宣传秒开。
目录手机视口检查不等于外站手机版验收。原始加载 / 超时和失败素材记录保留，不能只报正面观察。
所有来源和证据在：
`C:/Users/phpxi/.codex/visualizations/2026/11/05/01a1a966-0b33-7c53-9384-b9a750ccae19/native-direct-games-release/`。

## 实际生产发布与验收

- 应用提交：`cbd1b4653d79a6c4fe3072a83497943529c4d773`，仅本批 11 个文件。
- [CI 41983448279](https://github.com/ixiaoyy/ParallelLines/actions/runs/41983448279) 成功，
  包含真实 MySQL 迁移 / 后端测试、前端 lint / 类型 / 构建与同一产物打包。
- [Deploy 41984445272](https://github.com/ixiaoyy/ParallelLines/actions/runs/41984445272) 成功。
  根代理实查服务器源码及 Web 运行镜像 revision 均为上述提交，API / Web 健康，worker 运行，
  Nginx / MySQL / Redis 镜像与发布前一致，公网 `/healthz` 正常。
- 生产 schema 已到 `0106_add_direct_game_sites`，新记录 ID 为 `239`、`240`、`241`。
  三个准确名称 / 分类 / 单游戏直达 URL / 完整作者及主页 / external / 可见状态均回读正确，初读浏览为零。
- 之前十二条原 ID 与其他字段、评分关联和浏览量前后核对完全保持；原九款仍隐藏。
  Canteen 浏览 6、Dungeon 浏览 1、其余旧目标 0 均未改变。公开项目 **227→230**，恰好新增本批三个 ID。
- 真实公共 `/catalog` 与 overview 均为 230，九隐藏目标未返回，两端搜索均无卡片。
  新三款在电脑 / 手机分别准确出现一次，链接、作者、试玩名称与分类正确。
- 六张真实卡片均已逐张实看：两张 `200 image/webp` 与 ZType `200 image/jpeg`，自然尺寸与清单一致，
  实际解码和裁切正常；ZType 为 `50% 100%`，飞船 / 敌词 / 激光保留，其他图保持 `50% 50%`。
- Tobias 一行两作品，tobspr Games 与 PhobosLab 搜索有效，两个作者 URL 正确；
  作者作品两图真实解码。根代理已查看六张生产卡片及两端共享作者作品截图。
- 两端 `pageerror=0`、无横向溢出，没有点击真实游戏或发产品 API 写请求；所有浏览器已关闭。
  没有重测外站完整玩法或扫描旧首屏 / 慢图，不把目录手机视口验收说成外站手机版通过。

`new-records-after.json`、旧记录前后快照与 `previous-records-preservation.json` 均在本地和生产恢复目录留存。
实际页面 / 公开 API 证据在本次可视化 `online/production-acceptance-summary.json`、`public-api-evidence.json`。
最终记录作为本批文档跟进提交，不重新构建或部署；实际运行应用仍以上述已验收应用提交为准。
