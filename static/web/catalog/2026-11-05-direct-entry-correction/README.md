# 直达入口修正与九款暂隐藏

## 用户确认范围

只把 Spectrum、Six Cats Under、The Final Earth 2 换成此前核实的直达地址；其余指定九款隐藏。
保留全部原记录、ID、评分和浏览量。用户已授权本次验证后只提交推送本批，并按原流程部署。
本批只有一份数据迁移 `0105_catalog_direct_entries`，前置 `0104_add_classic_web_games`，无表结构变更。

## 十二条目标与字段变化

| 生产 ID | slug / 游戏 | 变化 |
| --- | --- | --- |
| 228 | `gd-spectrum` / Spectrum | 只改 `destination_url` |
| 234 | `itch-six-cats-under` / Six Cats Under | 只改 `destination_url` |
| 235 | `itch-the-final-earth-2` / The Final Earth 2 | 只改 `destination_url` |
| 229 | `gd-fungi-run` / Fungi Run | 只置 `is_visible=false` |
| 230 | `gd-super-chicken-td` / Super Chicken TD | 同上 |
| 231 | `gd-golf-adventures-2` / Golf Adventures! 2 | 同上 |
| 232 | `gd-helicopter-sos` / Helicopter SOS | 同上 |
| 233 | `gd-rocket-racers` / Rocket Racers | 同上 |
| 74 | `astra-940973d6b1805a52c1f0` / Mystery Town | 同上 |
| 58 | `astra-ca4e89010438edf3221e` / Canteen Crashers | 同上 |
| 110 | `astra-0a5696802efe2cf4eb0b` / MUST. MAKE. PAPERCLIPS. | 同上 |
| 130 | `astra-0751dc4e0b9b7bc13c1f` / Dungeon of Astra | 同上 |

迁移按稳定 slug 查实际 ID，不把生产 ID 硬编码到其他环境。首写前齐查十二款并确认三个原 URL；
已是目标直达地址时跳过，未知人工入口明确失败，不用新值覆盖。短保存点包本批更新，原值 CAS 或 SQL
失败时回滚已做的本批更新，不提交外层迁移事务。隐藏项不改原链接，已经隐藏的不重新展示。
没有 INSERT / DELETE，不写其他项目属性、时间、作者、封面、分类、排序、浏览或用户 / AI 评分表。

### 三个新链接

- Spectrum：[直接游戏文档](https://html-classic.itch.zone/html/7294044/Spectrum%201.1/index.html?v=1782787944)
- Six Cats Under：[直接游戏文档](https://html-classic.itch.zone/html/2267583/index.html)
- The Final Earth 2：[直接游戏文档](https://html-classic.itch.zone/html/1995721-336862/index.html)

它们分别来自作者公开 iframe 或此前官方页面合法读取到的公开游戏文档，匿名独立打开已见游戏自身菜单。
Spectrum 还验证了 Play → New Game 菜单切换；其余只核到菜单，不写成完整开局或通关通过。
这些是带发布版本路径的技术入口，长期稳定性没有保证；Spectrum 的作者另一发行版本尚未与 gd.games 构建逐字节比较。

## 保留行为及消费者

公开完整目录、概览计数、推荐、分类分页与 SEO 均沿既有可见性过滤；隐藏项目的浏览和评分写入口仍返回既有 404。
评分、想玩和最近打开按项目 ID 关联，封面按 slug；因此无需改 API、前端生产逻辑或封面映射。
浏览器本地清单中的隐藏 ID 不删除，重新获取公开目录后不渲染为可点击卡片。
公开进程缓存最多 60 秒；本批重启服务会清进程缓存，但不能承诺所有已经打开的旧前端页面即时更新，验收使用重新取数。
投稿审核仍按当前 URL 去重；旧平台地址不自动作为新直达地址别名，本批不扩展别名体系。

## 验证与发布前恢复

- 独立内存 SQLite 回归 30 passed，另语法、定向 Ruff 和空白检查通过。
  覆盖精确 3/9、原 ID / 其他字段 / 非零用户评分及 AI 表哨兵保留、幂等、已隐藏状态、缺目标、
  人工 URL、CAS 未匹配及中途 SQL 失败回滚；不冒充真实 MySQL 并发验收。
- 本地 Web 电脑 1280×900 / 手机 390×844 首轮 2 passed，检查三个准确直达 URL、旧正式图片解码与裁切、
  九名称搜索不出现、预存想玩 / 最近打开 ID 不泄漏但原 localStorage 保留，以及本地隔离打开统计。
  本次未改图片或静态资源映射，没有新增图片上传、压缩、清缓存或外站重复试玩。
- 初始真实 MySQL schema 为 `0104`，十二目标全部可见，公开项目共 236；
  十二条的用户评分 / AI 评测关联当前均为 0，非零保留另由离线回归覆盖。
  Canteen 浏览量 6，Dungeon 浏览量 1，其余 0。表无触发器或 `updated_at` 自动更新时间规则。

前值快照、源代码版本与旧 API / worker / Web 镜像标签已保存在生产：
`/data/releases/catalog-direct-entries-20261105-01a1a966/`。
`before-state.json` 含十二条完整项目字段、有限评分关联和公开 ID，不含评分 IP 摘要或评分人身份。
独立恢复服务入口 `recover-services.sh` / `rollback.yml` 已准备并核 shell 语法；
旧 API 恢复时跳过 Alembic 启动，不要求旧镜像识别 `0105`，不改 MySQL / Redis / Nginx 镜像或数据卷。

`downgrade()` 仅退版本，不自动重新展示或回写平台地址，避免覆盖后续人工维护。
如需恢复目录字段，应对照本批前值快照另行确认，只恢复本批配置字段，不回写浏览量或评分。
本地快照、数据保留核验和截图位于：
`C:/Users/phpxi/.codex/visualizations/2026/11/05/01a1a966-0b33-7c53-9384-b9a750ccae19/direct-entry-correction/`。

## 生产发布与验收结果

- 应用提交：`21b129bfc65340831f923de4492b4271e7722dc4`，仅本批四个文件。
- [CI 41974057029](https://github.com/ixiaoyy/ParallelLines/actions/runs/41974057029) 成功；
  原流水线真实 MySQL 迁移 / 后端测试与前端 lint / 类型 / 构建及同一产物打包通过。
- [Deploy 41974795342](https://github.com/ixiaoyy/ParallelLines/actions/runs/41974795342) 成功；
  实际发布 API、worker、Web，full-stack 与 Nginx 独立任务按范围跳过。
- 实际服务器源码和 Web 运行镜像 revision 均为上述提交，API / Web 健康，worker 运行；
  Nginx、MySQL、Redis 镜像与发布前一致，公网 `/healthz` 正常。
- 真实 MySQL 当前为 `0105_catalog_direct_entries`。前后十二条全部原 ID 保留，
  **严格只有三条目的 URL 和九条可见性改变**，其他项目字段（含时间、分类、作者、封面和排序）完全一致。
- Canteen 浏览量 `6→6`，Dungeon `1→1`，其余目标 `0→0`；十二条用户评分 / AI 评分关联前后均为零。
  非零评分和 AI 表保留由离线回归覆盖，不把零数据回读写成非零业务样本验证。
- 实际公开项目 **236→227**，正好隐藏九个指定 ID，没有其他可见项目新增或消失。
- 生产浏览器电脑 / 手机两端：九名称搜索均无卡片；三款存留项目各准确出现一条，
  精确新 href（含 Spectrum 版本查询参数）、`target` / `rel` 正确。
- 三张既有正式封面在真实卡片均返回 `200 image/webp` 并解码，尺寸仍为
  `320×180`、`630×500`、`1200×800`，根代理已实看六张卡片和两端隐藏搜索空状态，裁切正常。
- 两端 `pageerror=0`、无横向溢出，没有产品 API 写请求。未点击真实外链、制造浏览或评分，
  未重新上传图片、重复外站试玩或扫描无关旧图片。所有隔离浏览器已关闭。

`after-state.json`、`preservation-result.json` 已与前值一同保存到生产恢复目录；本地完整证据在
可视化目录 `direct-entry-correction/online/production-acceptance-summary.json`、`public-api-evidence.json`。
最终记录作为本批文档跟进提交，不重复构建或部署；运行应用仍以上述已验收应用提交为准。
