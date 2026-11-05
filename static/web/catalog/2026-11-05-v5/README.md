# 五款直玩游戏收录（2026-11-05）

## 已确认范围

用户确认本批五款与正式封面，验证后只提交推送本批到 `ixiaoyy/ParallelLines` 的 `main`，先上传封面，再按原 CI → Deploy 发布到 `pingxingxian.space`。
不汉化、不联系作者、不托管游戏包，不新增联系按钮、邮箱字段或作者归并算法。
保留旧记录、评分、浏览量和九款隐藏状态；仅额外获准将 BIRDLAND 的原作者作品页链接改为作者官网，与 Known Unknowns 合为同一作者条目。

| slug / 名称 | 分类 | 游戏直达入口 | 署名 / 作者链接 / 来源 |
| --- | --- | --- | --- |
| `her-tears-were-my-light` / 她的眼泪曾是我的光芒（Her Tears Were My Light） | `romance` 恋爱 | [官方公开游戏 frame](https://html-classic.itch.zone/html/18220499/index.html?v=1783279519) | NomnomNami / Emmit / LydianChord；[作者主页](https://nomnomnami.itch.io/)、[作品说明](https://nomnomnami.itch.io/her-tears-were-my-light) |
| `farmhand` / Farmhand | `farming` 种田 | [原版](https://jeremyckahn.github.io/farmhand/) | Jeremy Kahn / Farmhand contributors；[作者主页](https://jeremyckahn.itch.io/)、[项目](https://github.com/jeremyckahn/farmhand) |
| `exhibit-of-sorrows` / Exhibit of Sorrows | `horror` 恐怖 | [官方公开游戏 frame](https://html-classic.itch.zone/html/14611877/index.html) | Maxim Tsai (adayofjoy) / Theresa Kao；[作者主页](https://adayofjoy.itch.io/)、[作品说明](https://adayofjoy.itch.io/exhibit-of-sorrows) |
| `known-unknowns` / Known Unknowns | `romance` 恋爱 | [官方第一章](https://known.zone/one) | Brendan Patrick Hennessy / Izzy Marbella；[共同作者官网](https://bphennessy.com/)、[作品说明](https://bphennessy.itch.io/known-unknowns) |
| `crosscode-demo` / CrossCode（网页试玩版） | `rpg` 角色扮演 | [官方网页 Demo](https://www.cross-code.com/en/start) | Radical Fish Games；[工作室](https://www.radicalfishgames.com/)、[试玩说明](https://www.cross-code.com/en/home) |

Nami 原生语言菜单与简中开始菜单已实际核对，免费网页版不含付费下载版照片棚与开发者评论，含轻度恐怖。
Known Unknowns 四章完整免费、英文、阅读较长，涉及校园感情与捉鬼、粗口和药物话题；第一章入口不写成全篇单页。
Farmhand 单人本地模式可玩，联网为可选；Exhibit 为英文恐怖短篇，包含惊吓和伤害表现。
CrossCode 本入口实际为 **0.7.1 beta Demo**，不把商业完整版剧情、内容或评分冒充该网页试玩。

## 数据迁移与不变项

`0108_add_five_browser_games.py` 前置 `0107_add_birdland`，无 DDL。先检查四个既有分类，再以短保存点覆盖本批写入。
新项目按固定 slug 或直达 URL 防重，包含隐藏和跨分类项目；仅规范化 URL **path** 的末尾斜线，完整保留 Nami 的版本 query，不把不同版本或无参数入口擅自视为同一个地址。
排序追加至包含隐藏记录的分类末尾，恋爱两款依次追加；默认浏览量零，不创建本站玩家评分或 AI 评测。

BIRDLAND 仅当原 slug、完整作者署名和原作者地址精确匹配时更新 `author_url`：
`https://bphennessy.itch.io/birdland` → `https://bphennessy.com/`。
其他字段（包括创建 / 更新时间）、显隐、评分及浏览量不动，人工维护的其他作者地址不覆盖。
回退迁移只退版本，不删游戏、评分或自动反写作者地址。

## 正式封面

正式目录为 `covers/`，公开前缀为 `https://img.pingxingxian.space/static/web/catalog/2026-11-05-v5/covers/`。
五张最终合计 **255,202 B**，均为真实画面或原作角色插画，不使用 Loading、平台页、纯标题或分类占位。
原图、对照图与会话记录仅留本批可视化目录，公开仓库只加入五张正式 WebP。

| 文件 | 来源与处理 | 最终尺寸 / 字节 | 权利与署名范围 |
| --- | --- | --- | --- |
| `her-tears-were-my-light.webp` | [作者公开角色头图](https://img.itch.zone/aW1nLzEwMTQ3ODQwLnBuZw%3D%3D/original/7igqRr.png)，完整构图从 1920×620 等比例缩小，无损 WebP | 480×155 / 77,632 B | 角色美术 NomnomNami；游戏背景 Emmit、音乐 LydianChord。版权保留的单图介绍缩略引用，不宣称单独开放许可 |
| `farmhand.webp` | 新匿名离线会话的真实田地与工具栏，1280×900 截图取 `[560,140,1280,740]`，最近邻等比例缩小，无损 WebP | 480×400 / 6,492 B | [美术 CC BY-NC-SA 4.0](https://github.com/jeremyckahn/farmhand)，同许可发布本缩略版本；用户已确认仅非商业介绍用途 |
| `exhibit-of-sorrows.webp` | [官方宣传 GIF](https://img.itch.zone/aW1nLzg3NTgyODYuZ2lm/original/7yhMme.gif) 第 0 帧，不放大，无损 WebP | 394×342 / 64,708 B | [素材 CC BY 4.0](https://adayofjoy.itch.io/exhibit-of-sorrows)，Maxim Tsai / Theresa Kao；不混用代码 Unlicense |
| `known-unknowns.webp` | [官方第一章引用的 Nadia 立绘](https://known.zone/img/nadia1.png)，保留尺寸、透明与完整构图，无损 WebP | 400×480 / 56,762 B | 插画 Izzy Marbella，游戏 Brendan Patrick Hennessy；版权保留的单图介绍缩略引用，IFDB 的个别许可不作为本站许可 |
| `crosscode-demo.webp` | 0.7.1 beta 实际原生菜单的 Lea / 城市插画，1280×900 截图取 `[880,250,1280,790]`，最近邻缩小，无损 WebP | 356×480 / 49,608 B | Radical Fish Games，版权保留的旧 Demo 介绍缩略引用，不冒称 CC 或新版宣传素材 |

同尺寸 PNG → WebP 对照分别为 Nami **124,480→77,632 B**、Farmhand **14,044→6,492 B**、
Exhibit **128,546→66,036 B**、Known **89,725→56,762 B**、CrossCode **64,780→49,608 B**，像素一致。
仓库优化脚本先预览五图，只有 Exhibit 可再以像素等价压缩为 **64,708 B**；仅对它执行 `--write`，另四张保持。
Farmhand 宣传 GIF 的 30 帧都是农夫动画，未冒充田地；新会话明确 `Play online=false`，只用虚拟余额买一粒种子后打开田地，未联机、造景、种植或收获。截图花草是原始田地状态。

公开[封面署名页](https://pingxingxian.space/licenses/catalog-covers.html)沿原有目录页脚入口扩充五项，包含各自来源、署名、许可或版权保留及加工说明。
这些图片不代表取得游戏包、全文汉化、其他素材再分发或作者背书。

## 原站评分资料

仅为 **2026-11-05** 的来源核对记录，不写入本站 `catalog_ratings`、AI 评分或热度。

| 作品页 | itch.io 分数 / 评分人数 |
| --- | --- |
| [Her Tears Were My Light](https://nomnomnami.itch.io/her-tears-were-my-light) | 4.8 / 5，1,471 |
| [Known Unknowns](https://bphennessy.itch.io/known-unknowns) | 4.8 / 5，90 |
| [Exhibit of Sorrows](https://adayofjoy.itch.io/exhibit-of-sorrows) | 4.8 / 5，2,511 |
| [Farmhand](https://jeremyckahn.itch.io/farmhand) | 3.8 / 5，仅 4 人，样本较少 |

未查到本份 CrossCode 网页 Demo 的独立评分，不用付费完整版口碑替代。

## 验证与发布进度

- API 独立 SQLite 初始 45 项通过；仅 URL 处理修正及新增用例后，25 项相关检查通过、23 项未受影响检查复用。最终语法 / Ruff / 空白检查通过，不代替真实 MySQL。
- 前端类型检查、上传脚本语法、五图实际格式 / 尺寸与唯一 v5 发布接线通过；旧 SVG / JPEG / WebP 媒体类型保持。
- 真实生产预检 schema `0107_add_birdland`，四分类齐全，新五款含隐藏无重复，公开 **231**；原十六条及评分 / AI 关联已只读留存，九隐藏保持。
- 五个新对象上传前均不存在；仅上传本批 v5 五图并回读。公开 GET 均 **200 image/webp**，尺寸正确、可解码，与本地字节一致；不覆盖旧资源或全局清缓存。

本地两端卡片及作者归并、限定提交推送、CI / Deploy 和最终真实数据 / 页面结果完成后补记，不以上传成功代替上线验收。
另一个聊天的 BIRDLAND 汉化工作与本批共享仓库，须协调暂存和发布顺序；不混提其 0109、程序、翻译或其他资源。

## 恢复与证据

生产恢复目录 `/data/releases/five-browser-games-20261105-01a1a966/` 已保存发布前源提交、API / worker / Web 固定镜像、原十六条记录和评分及独立 `recover.sh`；恢复脚本语法检查通过。
旧 API 回退镜像启动时跳过 Alembic，避免无法识别新版本；不自动删除五款、降级数据、恢复全库或反写已批准的作者官网链接。
若需撤下新条目，另经明确授权使用管理员隐藏，保留记录、评分、浏览量。
独立健康检查为 `curl -fsS --connect-timeout 5 --max-time 20 https://pingxingxian.space/healthz`。

本地证据位于本次可视化 `five-games-release/`：数据合同 / 资产清单、优化报告、`records-before.json`、`public-images/verification.json` 与各源图、后续 QA / 发布记录。
