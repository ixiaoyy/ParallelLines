# 圈子三时段内容 worker

本材料只管理独立内容容器 `parallellines-community-content`，不停止、重启或重建原 API、旧 worker、Web、数据库、网关、Chat 等服务。发布权限按用户当次授权判断，本文及脚本不会延续授权。

## 当前上线版本：20261117-overseas-render

2026-11-17，按用户当次上线授权，已切换海外动态版本。首版 `20261117-overseas` 以当时运行的独立 worker 镜像 `31adfcf9719c` 为基底，只覆盖采集和调度所需三个文件；随后首轮真实发布暴露长标签/转义兼容问题，以首版镜像 `cccb5fadb4f5` 为基底，仅覆盖 `scheduled_content.py` 发布渲染修订。现用容器 `bf540a9de230`、镜像 `18583c4e39dd`。没有把其他工作区改动、API 新版本或完整 h1 模板一并发布；两次前像容器和旧版本目录均保留，原 h1 管理记录未覆盖。

独立入口及恢复步骤见 [当前修订发布手册](releases/20261117-overseas-render/RUNBOOK.md)，首版过程见 [海外接入手册](releases/20261117-overseas/RUNBOOK.md)。当前健康入口：

```sh
python3 /opt/parallellines/.deployment/community-content/20261117-overseas-render/rollout.py status
```

两版的发布工具源码共用 [rollout.py](releases/rollout.py)。后续获准交付时，把同一源码以 `rollout.py` 复制到本次选定的原版本目录，不使用跨版本软链接。脚本按固定目录选择该版本的覆盖和恢复目标，原命令与运行记录不变；已安装的脚本不会因本地合并被替换。

已核现用修订 Docker healthy、新实例启动后的有效心跳、实际运行源码与150字标签 helper；首版已核原激活水位、挂载、开关和单实例锁。两次切换均核其他容器 ID/启动时间不变。服务器侧来源预览四源无错误；当天 `18:00` 六个自然任务全部 `succeeded`，海外任务 `52149` 首次尝试发布 [topic802](https://forum.pingxingxian.space/topics/802/about-10-of-people-have-significant-trouble-identifying-their-get-some-quality-open-world-games-in-the-survival-of-the-fittest)，五条来源、五条 SOURCE 防重审计和唯一 SLOT 回执。

用户另行确认后，通过原作者的 `ForumService.update_post` 修正 topic802 首帖 `1216` 格式，原稿保存为 revision `58`；标题、作者、五条链接/时间/顺序及11条原发布审计均未改变，没有重发。匿名公开页面与帖子接口均返回 `200`，接口中的渲染 HTML 已核五个原帖链接可点击、顺序一致且无多余反斜杠。浏览器验收工具连接超时；独立协作者检查原生窗口后，也未找到能明确归属本任务的圈子窗口，未触碰其他页面。视觉复核待用户打开上述公开帖子形成明确任务窗口后由 AI 继续，不以接口结果冒充截图验收。

## 完整模板清单（非本次最小覆盖包）

以下为本地完整模板源码清单，不表示原服务器 h1 目录含本次新增模块；现有环境不应重跑 h1 的首次安装入口。本次版本包和恢复镜像清单见上述发布手册。

```text
manage.py
Dockerfile
context/
  app/core/community_content.py
  app/services/community_schedule.py
  app/services/scheduled_content.py
  app/services/overseas_content.py
  app/services/living_forum.py
  app/services/daily_reading.py
  app/services/daily_reading_provider.py
  app/workers/community_content.py
  app/workers/community_content_health.py
  scripts/collect_weibo_hot_search.py
  scripts/plan_living_forum_day.py
  scripts/publish_daily_reading.py
```

首次安装模板只上传这份明确清单，不打包整个工作区、`.env`、密钥或其他未提交改动；本次最小覆盖则使用各版本手册中的清单。脚本拒绝缺失、额外文件和指向交付目录外的来源链接。交付后由脚本生成非敏感 `build.json`、`state.json`、部署锁文件及持久快照目录 `var/`。

## 海外动态来源与行为（2026-11-17 接入）

新增 `overseas` 栏目，调用链为 `community_schedule` → 独立 `community_content` worker → `ScheduledContentService` → 原有 `ForumService.create_topic`。沿用 `小瓜同学` 专用身份和 `lounge` 公开版块，标签为 `海外动态`，不创建账号或版块，不新增表、迁移、依赖或环境配置。

固定公开账号如下；身份与本机公开接口于 2026-11-17 核对，不代表服务器连通或长期可用：

| 平台 | 账号 | 原站身份依据 | 内容 |
| --- | --- | --- | --- |
| Bluesky | `us.theguardian.com` | [Guardian 美国版页脚](https://www.theguardian.com/us) | 综合资讯，英语 |
| Bluesky | `gamingonlinux.com` | [GamingOnLinux 站长资料](https://www.gamingonlinux.com/profiles/liamd/) | 游戏、Linux，英语 |
| Mastodon | `gamingonlinux@mastodon.social` | 同上，原站同时链接两个账号 | 游戏、Linux，英语 |
| Mastodon | `heiseonline@social.heise.de` | [Heise 原站账号说明](https://www.heise.de/news/Twitter-Alternative-ARD-eroeffnet-eigene-Mastodon-Instanz-mit-Tagesschau-Account-8988570.html)及账号验证字段 | 科技，德语 |

- 每个原有时段增加一个独立任务，最多发布一篇、一至五条的新动态合集，不要求凑满。各账号轮流取样；同一原帖、无文章外链的同内容或同一出版站文章在两平台同步时去重。每条原帖和内容/文章防重标识与时段回执同事务保存，崩溃重试不重发已确认内容。
- 四个白名单 JSON 端点并行读取，每个最多五条；连接/单次读超时 10 秒、每请求总限 25 秒、响应上限 2 MiB，不跟随重定向、不下载正文或媒体、不访问返回内容中的其他地址。只接收身份匹配、48 小时内、带时区时间的公开原创，排除回复、转发、引用帖及敏感/警告标记内容。明显未来时间也不收录。
- 合集保留作者、平台、原帖链接、原帖时间和有长度上限的原文短摘；不提供自动翻译或独立事实核实，不新增模型/接口费用。新闻、体育、微博热搜、读书不变；生活小问、旧自动任务和浏览器通知不恢复。
- 健康但无新内容正常跳过；部分来源失败记录稳定来源名/异常类型，其他来源仍可使用；全部来源不可用明确失败，仅暂态网络错误进入现有三次有界重试，不拿旧内容代替成功。

本地验证记录：

- 三个定向测试文件共 93 项已通过，覆盖新来源解析/过滤、文章外链与无卡片富文本链接去重、单条审计与合集事务接线、时段重试/预览无写入，以及原五项调用不变。首轮 88 项通过；另三个新测试的专用账号 fixture 错用了身份类型，修正为现有 `editorial` 后通过；两个旧测试遇默认系统临时目录权限错误，改用本任务专属临时目录后通过。标题词边界缩略另做了受影响单项回归，已通过。没有连接测试库或生产库。
- 新采集模块及其新测试的 Ruff 检查、交付管理脚本语法检查通过；相关改动空白检查通过。
- 北京时间 2026-11-17 16:45，沿实际采集/组稿调用链只读四个公开端点，取得 20 条候选、按单条/文章防重后 15 条，生成五条合集预览，`source_errors=[]`。标题调整沿用这次保留的短摘重组，没有重复抓取。来源接入与防重实测不等于真实数据库事务或公开页面验收。

上述 93 项回归与本机采集属于最初本地阶段，不证明上线结果；后续已获用户当次上线授权，当前部署与未完成验收见本文顶部。旧 `20261115-h1` 记录不代表海外模块已发布，本次使用独立新版本入口，未覆盖旧目录或删除状态绕过守卫。

## h1 首次安装参考（现有环境不要运行）

先独立核对专用账号、公开版块、来源连通、数据库版本和当次源码。再在服务器执行：

```sh
cd /opt/parallellines/.deployment/community-content/20261115-h1
python3 manage.py build
python3 manage.py install
python3 manage.py status
```

- 基底必须仍是已核实的现用 API 镜像 `sha256:4f2e43c0ee4a95c93734b075be7860cf2e4ce1407c1603f8f8689a309e4e00ea`；只增加本地基底标签，使用 `--network=none --pull=false` 构建最小覆盖镜像，不安装依赖或拉取镜像。
- 新容器连接既有 `parallellines_default` 网络，引用既有 `/opt/parallellines/apps/api/.env`，不读取输出或修改其中的值；不暴露端口。
- 本容器资源上限为内存 `512 MiB`、CPU `0.5` 核、进程 `128` 个；独立 JSON 日志每份最多 `10 MB`，保留三份，不扩散共享主机资源。
- 仅本容器设置 `COMMUNITY_CONTENT_ENABLED=true`、当前 UTC 激活水位、读书发布模式 `auto`；生活发布模式显式为 `off`。读书新用法显式选择 `local`，不新增付费模型调用；不改变原服务的模型配置。
- 快照持久挂载到本交付的 `var/`，容器内路径为 `/app/var`。
- 每天北京时间 `10:00`、`14:00`、`18:00`，微博采集、新闻、体育、热搜、读书、海外动态六项分别入队，周末也运行。生活小问不再入队或调用发布服务；已排队的生活任务仅记为 `skipped/living_retired`，不再发帖，也不删除历史帖子或账号。激活前、前日和超过当前时段宽限窗口的任务不补发；没有可靠新来源时按内容服务结果跳过，不拿旧稿补数量。
- 固定容器名、版本/路径/事务标签及安装前像共同限定所有权。重跑 `install` 只接受同事务、同镜像、仍在运行且重启策略正确的现有容器，不覆盖外部容器，也不把已停止容器偷偷启动。

`install` 成功仅表示新容器已启动、其他容器 ID 未变化，**不代表健康检查或首次实际发布通过**。刚启动时 `health_pending=true` 属待验收状态；等待初始化后运行 `status`。worker 另以独立数据库连接持有命名锁，防止第二实例抢任务；仍不得为了验收启动第二个常驻实例或与它并行运行 `--once`。

## 独立健康与恢复

`python3 manage.py status` 只读检查容器身份、Docker 健康状态及最近完成过数据库轮询的心跳；不会执行采集、入队或发布。它不证明新闻来源可用、账号实际发布成功或每个栏目都有新内容。应另查本独立队列的时段结果及公开页面；不得把健康状态当作真实发帖验收。

需要恢复为未启用内容发布时，仅在当次授权内执行：

```sh
python3 manage.py stop
python3 manage.py status
```

`stop` 先核对本版本精确容器、镜像和事务，关闭其自动重启，再仅停止该容器；保留已发布内容、快照、状态、镜像及其他服务。它不删除已发布帖子、不清理队列、不回滚数据库、不删除任何容器，也不恢复旧自动任务。状态会显示容器已停止，健康 `complete=false` 是预期结果。恢复后重新启用属于新的明确操作；本入口不会静默重启已停止实例。

命令超时或失败时保留安装前像，不盲目删除、重建或重复发布。`docker run` 可能已成功但回执丢失，可先运行独立 `status`；仍需重复 `install` 时只允许接续同事务的已存实例。遇容器、镜像、状态或其他容器身份漂移则停止并报告，禁止强制覆盖。原始 Docker 错误输出不打印到报告，报告只含稳定错误码，避免泄露环境值。
