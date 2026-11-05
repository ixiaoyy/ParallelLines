# 2026-11-05 外链网页游戏收录

## 范围与资料

本批追加四款作品，继续使用 `external` 类型：目录 API → 游戏卡片 → 新标签打开原站。
不嵌入或分发游戏包，不标记为 AI 生成，不改旧记录、评分、浏览量或目录布局。
用户已授权本地收录、正式封面、图片上传、仅本批提交推送到 `main`，以及生产部署。

| slug | 分类 | 作品入口 | 作者与作者链接 |
| --- | --- | --- | --- |
| `gd-helicopter-sos` | `simulation` / 模拟经营 | [Helicopter SOS](https://gd.games/malaspina/helicopter-sos) | [Malaespina](https://gd.games/Malaespina)，不按入口路径误写为 malaspina。 |
| `gd-rocket-racers` | `racing` / 竞速 | [Rocket Racers](https://gd.games/tulenvakiproductions/rocket-racers) | [TulenvakiProductions](https://gd.games/TulenvakiProductions)。 |
| `itch-six-cats-under` | `puzzle` / 解谜 | [Six Cats Under](https://teambeanloop.itch.io/six-cats-under) | Team Bean Loop / Mosu；作者链接使用列出双方的作品页。作品页另列 Miles Äijälä、Robin Swift、Tomas Beržinskas、Alex Martin 的制作署名。 |
| `itch-the-final-earth-2` | `simulation` / 模拟经营 | [The Final Earth 2](https://flori9.itch.io/the-final-earth-2) | [Florian van Strien](https://flori9.itch.io)。 |

玩法简介仅采用作者公开资料：机械臂救援、飞船避障、幽灵解谜救猫与太空城市经营。
The Final Earth 2 链接为网页基础版，Steam 与手机扩展版另售，不把扩展版功能写入本入口。
Rocket Racers 的手机双人模式未实测，不宣传为已验证多人游戏。

## 正式封面

所有图片来自对应作品的官方页面，已实际查看原图与最终图；不使用纯文字或分类占位图。
正式路径为 `static/web/catalog/2026-11-05-v1/covers/`，四张合计 **125,816 字节**。

| 文件 | 来源 | 原尺寸 / 字节 | 最终尺寸 / WebP 字节 | 处理 |
| --- | --- | --- | --- | --- |
| `gd-helicopter-sos.webp` | [官方分享封面](https://games.gdevelop-app.com/game-d3fa48b8-7651-40ca-adb8-3d49efa1ceb1/foto1%20-%20lilou.png) | 1920×1080 / 43,500 | 1280×720 / 11,660 | 最近邻缩小后无损 WebP；直升机和被救者可见，非纯标题。 |
| `gd-rocket-racers.webp` | [官方实机截图](https://public-game-resources.gdevelop.io/29756cdb-7d2b-4081-b144-af556da68923/screenshots/screenshot_9914a91b-7c15-4be2-a0c3-4d522ab2aca6.png) | 836×1280 / 187,074 | 836×1280 / 103,102 | 无损 WebP，保留竖图、飞船与星空；未使用菜单图。 |
| `itch-six-cats-under.webp` | [作者分享封面](https://img.itch.zone/aW1nLzM0NjMwNjMucG5n/original/y4bpPK.png) | 630×500 / 15,180 | 630×500 / 5,746 | 无损 WebP，保留像素猫咪、房间与透明通道。 |
| `itch-the-final-earth-2.webp` | [作者分享封面](https://img.itch.zone/aW1nLzIyMTU1NDAucG5n/original/6vGlZe.png) | 1200×800 / 43,730 | 1200×800 / 5,308 | 无损 WebP，保留太空殖民地构图。 |

原图合计 289,484 字节，最终减少约 56.54%。图片没有裁切或铺底；只有 Helicopter 按卡片需求缩小。
仓库 `optimize_static_images.py --write` 对前三张再进行像素等价压缩，共减少 1,118 字节；
Final Earth 已无更小的等价输出，因此保留，不重复有损编码。
Helicopter 的 Lanczos 缩小候选达 121,112 字节，且会改变像素边缘，未采用。
Rocket 的偏暗星空来自官方实机，不人为增亮或编造画面；页面仍须检查飞船可辨识与裁切。

原图、未选候选、来源 JSON 和压缩记录保存在本次聊天的可视化目录：
`C:/Users/phpxi/.codex/visualizations/2026/11/05/01a1a966-0b33-7c53-9384-b9a750ccae19/more-web-games/`。
来源记录用于目录展示溯源，不代表取得游戏包或素材再分发许可。

## 同批交付与部署顺序

以下内容必须同批交付，不能只发布数据而漏图：

- `apps/api/alembic/versions/0103_add_more_web_games.py`
- `apps/web/src/features/catalog/coverManifest.ts` 的四项正式图片映射
- `apps/web/src/features/catalog/coverAspectManifest.ts` 的四项真实宽高比
- `apps/api/scripts/upload_static_web_assets.py` 的四个静态 key
- 本目录的四张 WebP、来源清单及本批定向回归

四个公开目标为：

- `https://img.pingxingxian.space/static/web/catalog/2026-11-05-v1/covers/gd-helicopter-sos.webp`
- `https://img.pingxingxian.space/static/web/catalog/2026-11-05-v1/covers/gd-rocket-racers.webp`
- `https://img.pingxingxian.space/static/web/catalog/2026-11-05-v1/covers/itch-six-cats-under.webp`
- `https://img.pingxingxian.space/static/web/catalog/2026-11-05-v1/covers/itch-the-final-earth-2.webp`

先用现有上传脚本限定 `--catalog-only --catalog-version 2026-11-05-v1 --verify` 上传；
确认公开图片返回 `200` 与图片类型，再部署 API 数据迁移和 Web 映射。
最后在真实目录逐款检查正确资料、图片地址、自然尺寸、裁切及外链，并保存截图。
存储回读或部署成功不能代替目录页面验收。

本批只有一份数据迁移，接在 `0102_add_selected_web_games` 后，不改表结构。
先确认三个分类齐全，再按固定 slug 或有无末尾斜线的地址防重；隐藏与跨分类记录同样保留。
新条目追加到包含隐藏记录的分类末尾，初始浏览量为零，不创建评分。
幂等不额外识别管理员自定义跟踪参数或其他等价地址。

## 验证与恢复边界

- 独立迁移回归 `apps/api/tests/test_catalog_more_web_games_migration.py`：18 passed，
  覆盖准确资料、防重、隐藏与跨分类保留、分类缺失前置终止、连续排序及非删除回退。
  仅内存 SQLite；96 条 Python SQLite datetime adapter 弃用警告，不代表真实 MySQL 验收。
- 新迁移与测试 `py_compile`、定向 Ruff 通过；不运行默认 `pnpm test:api`。
- Web 定向回归使用当前发现页、分类、搜索和作者榜；现有 UI 无旧版网格/列表切换，
  不为本次收录新增页面模式。
- 本地 Web 电脑与手机定向回归 2 passed；手机截图避开既有固定导航后定向 1 passed，
  桌面路径未改。根代理已查看两端发现页与四款手机卡片；图片内容可识别，Rocket 原图偏暗。
  `pnpm typecheck:web`、新 smoke 定向 ESLint、上传脚本语法与定向 Ruff、diff 空白检查通过。
- 四张新版本图片上传前均确认为新对象，实际上传与存储回读通过；公开 GET 全部 `200 image/webp`，
  字节与本地一致且可解码。没有覆盖旧对象或清缓存。
- 四个原站入口均实际返回 `200`，未遇强制登录或付费拦截。The Final Earth 2 已进入殖民地画面，
  开始与教程关闭按钮有正常响应，未做建造长测。其余三款约 80 秒仍在 GDevelop / Unity 加载器；
  Rocket 另报 `Permissions check failed`，未接受权限或绕过，不能宣称三款试玩通过。
  隔离浏览器已关闭；完整外站报告与实际截图位于可视化目录 `gd-assets/external-play/`。
- 初始只读生产检查：主站 `/healthz` 为 `200`，API 与 Web 健康，迁移为 `0102`。
  真实 MySQL 中三个分类齐全，四个 slug 或外链均未存在。本批部署及最终页面验收尚未完成。

`downgrade()` 只回退版本号，不删除作品或其评分、人工编辑；撤下单款使用管理员隐藏入口。
恢复前端时保留旧版本对象与旧镜像，不清全局缓存或删除资源。
部署前固定实际 API、worker、Web 镜像与独立健康检查，避免影响 MySQL、Redis、上传与备份卷。
本批部署前已固定三个镜像的 `parallellines-rollback-<service>:more-web-games-20261105` 标签，
恢复目录为生产服务器 `/data/releases/more-web-games-20261105-01a1a966/`。
其中 `recover.sh` 与 `rollback.yml` 可恢复原镜像，健康检查独立使用公网 `/healthz`；
旧 API 恢复时跳过迁移启动，避免旧镜像不识别 `0103`，不回写或删除业务数据。
