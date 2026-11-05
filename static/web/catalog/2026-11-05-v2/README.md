# 2026-11-05 第二批经典网页游戏收录

## 范围与来源

用户已确认本批三款、正式封面、验证后仅本批提交推送到 `main`，并上传部署到现有生产站。
继续使用 `external`：目录 API → 游戏卡片 → 新标签打开原站，不嵌入或托管游戏包，不标记 AI 生成。
不改表结构、已有项目、评分、浏览量或目录布局。

| slug | 分类 | 正式入口 | 完整作者 / 作者链接 |
| --- | --- | --- | --- |
| `choppy-orc` | `stages` / 闯关 | [Choppy Orc](https://eddynardo.com/games/choppy-orc/) | [eddynardo](https://eddynardo.com/) |
| `0hh1` | `puzzle` / 解谜 | [0h h1](https://0hh1.com/) | Q42 / Martin Kool；[Q42 官方主页](https://www.q42.nl/en) |
| `0hn0` | `puzzle` / 解谜 | [0h n0](https://0hn0.com/) | Q42 / Martin Kool；同一 Q42 官方主页 |

Choppy Orc 官网另署美术 `0×72`、`Adam Saltsman`；音乐为 `Rolemusic` 的 `The Little Broth`，
官网注明 CC BY 4.0。本站只展示真实游戏画面与链接，不复制游戏音频或游戏包。
它与页面顶部宣传的 Super Choppy Orc 是不同作品，不能混用后者的横幅或名称。

0h h1 采用双色逻辑填格规则，不把当前主题颜色固定为红蓝；0h n0 采用数字视线和红点阻隔规则。
两个 Q42 条目保留完整创作者署名并共用作者 URL，使现有作者榜聚合为一行两款；
榜单沿现有规则显示主作者 Q42，搜索仍覆盖 Martin Kool，不改作者归并逻辑。

## 正式封面与体积

正式图片均为官方网页实际运行画面，保留原始截图；没有制作虚构画面或用通用色块占位。
两款 Q42 图直接截取真实 `#grid` 整张教学棋盘，不包含教学文字、工具按钮或浏览器边框。
这是游戏本身的方格 / 圆点画面，不使用只有三个色块的 0h h1 官方宣传图。

| 文件 | 实际来源 | 原 PNG 尺寸 / 字节 | 最终尺寸 / WebP 字节 |
| --- | --- | --- | --- |
| `choppy-orc.webp` | 作者页内官方 Netlify 游戏画布，实际一级移动及投斧后的截图 | 640×361 / 6,372 | 640×361 / 2,642 |
| `0hh1.webp` | `https://0hh1.com/`，正常教学输入后的完整棋盘元素 | 600×600 / 9,053 | 600×600 / 2,496 |
| `0hn0.webp` | `https://0hn0.com/`，数字视线教学的完整棋盘元素 | 580×580 / 26,808 | 580×580 / 10,838 |

三图均为无损 WebP，未放大、拼贴、铺底或改游戏状态，最终共 **15,976 字节**。
原 PNG 共 42,233 字节；压缩节省约 62.17%。Choppy 原画布截图实际高 361，保留这 1 像素，不伪报 360。
仓库 `optimize_static_images.py --write` 对 Choppy 再无损减少 2 字节；两张 Q42 已无更小的像素等价结果，
不重复有损压缩。封面宽高比清单分别记录 `640/361`、`1`、`1`。

原图、编码和正常操作记录在本次可视化目录：
`C:/Users/phpxi/.codex/visualizations/2026/11/05/01a1a966-0b33-7c53-9384-b9a750ccae19/next-web-games/`。
`assets/delivery.json` 记录各图处理，`assets/browser-evidence.json` 保留教学未完成等限制。
来源记录用于目录展示溯源，不代表取得游戏包或其他素材再分发许可。

## 同批文件与发布

- `apps/api/alembic/versions/0104_add_classic_web_games.py`
- `apps/web/src/features/catalog/coverManifest.ts`：三个正式 slug 映射
- `apps/web/src/features/catalog/coverAspectManifest.ts`：三个真实宽高比
- `apps/api/scripts/upload_static_web_assets.py`：三个同版本静态 key
- 本目录三张 WebP、本来源清单及 API / Web 定向回归

公开目标统一为 `https://img.pingxingxian.space/static/web/catalog/2026-11-05-v2/covers/` 下的三个文件。
先限定 `--catalog-only --catalog-version 2026-11-05-v2 --verify` 上传，公开图片返回 `200 image/webp` 后，
再通过原 CI → Deploy 发布 API 数据迁移和 Web 映射；最后逐款核对真实两端卡片，不以部署成功代替页面验收。

`0104_add_classic_web_games` 接在 `0103_add_more_web_games` 后，只有一份数据迁移，不改表结构。
先核齐 stages / puzzle 分类，再按固定 slug 或有无末尾斜线的入口防重，包含隐藏和跨分类记录；
人工编辑和统计不覆盖，新条目追加到包含隐藏记录的分类末尾，默认浏览量零，不创建评分。
不额外识别管理员自定义跟踪参数；上线前后均需核对实际记录。

## 验证与恢复

- API 独立 SQLite 回归：15 passed；60 条 Python datetime adapter 弃用警告，无失败。
  覆盖准确资料、共享 Q42 作者 URL、防重、分类前置终止、排序、旧数据和非删除回退。
  只证明离线迁移合同，不等同生产 MySQL 验收。
- 原站正常启动：Choppy 已到一级并实际移动、投斧；0h h1 已有教学填格反馈；0h n0 已展示教学视线规则。
  后续封面采集两款 Q42 正常推进教学后仍未完成，因此不宣称自由模式填格或完整通关通过。
  没有改 localStorage、注入状态或跳过权限；未测试外站手机玩法。
- 初始生产只读检查：公网 `/healthz` 正常，schema 为 `0103`，两个分类齐全，本批三个 slug / 入口无重复。
- 本批服务恢复目录：`/data/releases/classic-web-games-20261105-01a1a966/`。
  API、worker、Web 已固定 `parallellines-rollback-<service>:classic-web-games-20261105` 镜像标签；
  `recover.sh` / `rollback.yml` 已准备并检查 shell 语法，独立健康检查为公网 `/healthz`。

`downgrade()` 不删除项目、评分或人工编辑。旧 API 恢复时跳过 Alembic 启动，避免旧镜像不识别 `0104`；
回退旧 Web 如需撤下本批，由管理员隐藏三条记录，服务恢复脚本不自动改业务数据。
旧静态对象、数据库 / Redis、上传与备份卷不清理，不做全局缓存清除。

本地电脑 1280×900、手机 390×844 的定向 Web 检查首轮 2 passed；
包含发现页分页、分类 / 搜索、三图准确自然尺寸 / 比例 / 裁切、旧图保留、外链新标签及本地打开统计，
以及 Q42 单行两作品、Martin Kool 搜索与作品入口。根代理已查看六张两端分类卡片，真实内容可辨。
棋盘图片按既有 `cover` 居中裁切，边缘部分格子 / 圆点裁掉，不改页面布局；手机横排原有翻页箭头保留。
本地 Vite 5193 已停止，`pnpm typecheck:web`、新 smoke 定向 ESLint、上传脚本语法 / Ruff、diff 空白检查通过。

三张 v2 图片上传前均确认为不存在的新对象，现已实际上传并存储回读通过；公开 GET 全部为
`200 image/webp`，字节与本地一致且可解码，没有覆盖旧对象或清缓存。
这些检查不代替上线后的真实目录验收；本批 CI、部署、生产 MySQL 和页面结果完成后另记。
