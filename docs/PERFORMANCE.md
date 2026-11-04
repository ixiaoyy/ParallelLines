# 性能优化与发布边界

## 范围

本批覆盖主站、工作区内的游戏与工具，以及相邻 Chat、模型 API 仓库。不包含 Fable 独立站、身份/计费规则变更、发布排空、维护门或新增 `503`。本文件描述实现和本地证据；提交、推送、实际部署与线上验收须分别记录。

## 页面与资源

- 游戏目录只让推荐首组或筛选结果的前三张封面立即加载，其中第一张设高优先级；后续分类仍懒加载。保留当前玉青目录、筛选、投稿及 AI 评分展示。
- Vite 根据实际 `VITE_STATIC_ASSET_BASE_URL` 为 HTTP(S) 静态域名生成 `preconnect`，相对路径不额外预连。已有 CDN 配置继续有效；这不代表 CDN 已命中。
- 新游戏图片和分类图集使用无损 WebP，原 PNG 保留，尺寸和 RGBA 内容相同。既有游戏素材保持同源；本次目录装饰与认证背景沿用 `staticAssetUrl` 的 CDN 前缀并切换到新的 `.webp` 地址。供新版引用的 23 个 CDN 对象已先上传并核对公开地址 `200/image/webp` 与字节，之后才能发布前端，不能只发 Web 镜像。
- Web Nginx 压缩文本资源。指纹 `/assets/` 使用一年不可变缓存；限定目录内非指纹公开图片使用一天缓存和后台重新验证。HTML、接口、上传资源不扩大缓存范围。
- 主站共享 Nginx 对 Chat、模型 API 只允许状态成功、类型明确的指纹资源长缓存，其余响应保持 `no-store`；不能用 CDN 全站缓存覆盖登录、个性接口或生成流。实测 Chat 缺失静态文件会回退为 `200 text/html`，因此不能只按 `/_app/immutable/` 前缀缓存。API 对应配置也保留在独立仓库的 vhost 模板中。
- 拼豆画布复用底图，缩放和聚焦不再重绘底图或重置缓冲；生成规则与导出保持不变。
- 回廊第 4 关只缓存固定装饰、复用实例缓冲，保留最新主分支的角色、门、支撑和移动子步修复。旧开发基线的 Float32 分配和耗时数据不能代替新组合或线上帧率；新主分支组合的冻结状态画面、GPU 数据和关卡状态等价检查单独留证。
- 主站 SEO 链接读取改为只查询所需字段，省去页面不使用的评分聚合；真实目录接口保留用户评分和 AI 汇总。

### 2026-11-04 图片压缩与懒加载

- 范围为仓库已跟踪的 `apps/web/public` 与 `static` 位图，共 312 张 PNG/WebP；跳过 7 张 Logo、favicon 或品牌图。不是整站接口图片迁移，不修改数据库里的头像地址、上传服务或用户原始附件。
- 离线工具为 `apps/api/scripts/optimize_static_images.py`，复用现有 Pillow 依赖。默认只预览，`--write` 才写入，`--report` 可保留逐图报告；可传明确的文件路径，默认全量处理已跟踪图片。只采用更小且尺寸、逐帧 RGBA、时长、循环和 ICC/EXIF/XMP 一致的结果。原 PNG 保留；已持久化的内置头像维持 PNG 地址。
- 对照任务开始的干净基线，实际变更 36 张图片：21 张新增 WebP、14 张原位 WebP 和 1 张原位 PNG；另有 8 张 PNG 可复用已有 WebP。新增 WebP 合计由 `25,532,472 B` 降至 `17,887,738 B`，减少约 29.94%；原位 WebP 减少 `78,376 B`，头像 PNG 减少 `23,000 B`。这是对应素材的合计，不是首页一次请求量，也不是保留原 PNG 后的仓库磁盘净减少。逐图来源、跳过项和原位优化结果见 `docs/image-optimization-20261104.json`。
- 目录装饰、认证背景、拼豆人像示例、西瓜图集及遗留游乐场图片引用已同步；CDN 清单增加新目录装饰和认证背景，保留旧对象与原 PNG 兼容路径。`upload_static_web_assets.py` 的既有目录版本过滤仍可定向预览新目录图片。
- 目录仍仅首组或筛选结果前三张封面立即加载，首张高优先级。园林装饰为低优先级懒加载，手机宽度不超过 760px 时选内嵌空图，避免仅 CSS 隐藏仍下载。榜单装饰、长列表头像、后台目录和工具示例补齐懒加载；Logo、关键作品、主头像、当前预览和即时游戏精灵保留及时加载。
- 项目 `AGENTS.md` 增补后续图片必须压缩检查、真实引用和发布清单同步、非首屏默认懒加载及手机隐藏大图避免下载的规则；写入规则不代表 CI 自动拦截。

本地验证：

- 已采用图片逐帧回读验证；其中动画头像框因编码器改变完全透明像素下的隐藏 RGB 被拒绝替换，保留原动画，没有放宽验收条件。
- 压缩工具独立 unittest 10 项、静态清单离线合同 5 项通过；不读取真实环境配置、不连接数据库或对象存储。Python 语法及相关 Ruff 检查通过。
- 目录资源优先级 SSR 测试 3 项通过。Windows SSR 下绝对 public 图片 URL 需要专用 `apps/web/vitest.catalog-resources.config.ts` 保留 URL 字符串，生产 Vite 配置不变。
- 全项目标准 `vue-tsc -b --pretty false` 通过。首次 pnpm 检查入口自动从本地缓存补齐 4 个已锁定依赖，下载数为零，依赖清单和锁文件未变；后续直接运行 Node 检查入口，没有继续安装。
- 真实本地隔离浏览器使用冻结的公开目录快照：电脑 `1440×1000`、手机 `390×844` 各检查 305 个图片元素，初始远屏延后候选分别 18/85 个，纵向与分类横向滚动后无未解码图片、错误图片响应或页面异常；手机园林图片请求为零。父级查看了电脑/手机首屏及恐怖/探索分类截图，布局与画面保持。
- 登录页分别读取 PC/H5 新背景；拼豆人像生成 64×64 图纸与 4096 颗材料；西瓜游戏的 9 张路线水果画布与实际投放精灵正常。证据在 `.tmp/image-optimization-20261104/final-browser-report.json` 和同目录截图，测试服务均已关闭。浏览器复用了保留工作区内与锁文件同版本的真实 FontAwesome 包，没有使用组件替身。
- 未启用的 `PlayHubPage.vue` 正式入口本就重定向首页，独立挂载仍有遗留路由名称缺失；本次仅其资源地址可达性通过，不宣称该旧页面整体可用，不扩范围恢复旧入口。

CDN 发布时发现 `gd-super-chicken-td.webp` 仍命中旧字节缓存，源站虽已更新但不能据此声称边缘已更新。本次增加 `gd-super-chicken-td-optimized.webp` 独立地址并同步封面映射、尺寸及发布清单，公开字节已验证；这份发布副本不计作原始 312 张批量压缩中的额外原图。没有清理全局缓存或修改 CDN 控制台规则。旧对象的恢复字节、本批 23 个供新版引用对象的收据保留在本地 `.tmp/catalog-release-20261104/`。

### 2026-11-04 按分类几何分批与公开缓存

- 默认发现页不再无条件请求完整 `/catalog`、创建 235 张卡片。新增 `/catalog/overview` 只返回真实分类计数及当前 6 张精选，分类接近纵向可视区后才按真实容器、卡片和间距宽度请求 `/catalog/categories/{slug}/projects`；横向靠尾、箭头及扩宽再补所需数据。mixed 按实际普通卡宽先估量并补齐三元组，响应后以真实边界补缺，不将最窄竖图宽度当整排常态；不存在全局固定 24 张限制。
- 分类接口实际执行 SQL `LIMIT(limit+1)` 和有界游标，游标绑定分类与种子同秒优先顺序，保留原创建时间/种子/数值 ID 排序；仅排列新完整三元组，已显示前缀不重排。正式封面真实尺寸清单在下载前参与几何计算，自定义未知尺寸不推测。远处分类保留结构占位，未激活时没有游戏卡片 DOM。
- overview 的专题候选仍由既有前端规则提供，不复制另一份游戏名单。省略 `hero_slugs` 表示全部，显式空串表示空候选；Hero 冷请求为准确评分排序仍需读取候选 ID/AI 评分，但完整卡片只读当前 6 张。搜索、作者/贡献榜、作者作品、想玩和最近打开才按需使用旧完整目录，不能以当前已加载前缀统计全部内容。
- 两个新公开响应使用独立 DTO，带真实 `category_slug`，`my_score` 始终为 `null`。旧 `/catalog`、评分、浏览写请求和后台的私有行为及响应不变；新公开请求不发送身份/访客头或 Cookie，不在接口缺失时静默回退全量取数。
- 服务端复用 256 条上限的进程内缓存，TTL 60 秒；响应使用 `public, no-cache`、ETag 和条件请求 304。浏览器可以保存公开正文但需协商重新验证；Vue Query 新鲜 60 秒、保留 10 分钟，返回分类/缩放复用已有游标页，屏宽和请求量不作为客户端页链缓存键。没有对所有 API 或 HTML 启用共享长缓存。
- 分类、项目、评分、浏览及批准投稿提交成功后清目录缓存，失败事务不失效；代次检查防止旧在途加载重新回填。跨 worker 与外部 AI 导入最多等待 60 秒自然失效，不把本进程 `clear()` 说成全局即时更新。成功写响应仍同步当前页面新旧缓存中的同游戏公共统计，不把个人分数写入公开缓存。
- 每分类串行请求、每个像素覆盖目标最多 4 次补页，单请求 8 秒；失败保留已载卡片并提供重试。离开附近停止继续补页、离页取消，near 重入按当前尾缘恢复；缩窄重置像素目标且不删除已载项目，不为填旧宽屏目标再取数据。

新阶段证据与发布边界：

- 后端 9 项独立 SQLite/ASGI 回归通过，覆盖真实 SQL 游标/排序/隐藏、公开 DTO 两 IP 隔离、缓存键/304/失效/代次以及旧评分和浏览语义；不是生产 MySQL 执行计划验证。
- 前端几何/稳定前缀 7 项、near 重入恢复定向 1 项、公共传输 4 项通过，原模型/专题/三元组 21 项有效证据保留。新源类型检查和定向 ESLint 通过，OpenAPI 与前端类型快照已同步。原图片等价检查不因分页改动重跑。
- 冻结的 229 项本地真实快照下，旧发现页为 235 张 DOM 卡片；电脑 `1440×1000` 初始 33 张/5 次公开请求、手机 `390×844` 初始 9 张/2 次公开请求，默认发现页均不请求旧全量接口。JSON 正文字节由旧约 154 KB 分别变为约 34 KB/17 KB；这是未压缩 fixture 数据，不是生产传输量、LCP 或网络测速。
- 电脑和手机最终 14 个非空分类的 ID 并集完整、无重复在途请求；搜索/榜单/未加载个人清单、局部失败重试、迟到响应隔离、横向追加、near 零等待恢复和宽→窄不新增请求均通过。中间 QA 的 about:blank、本帧 IO 与等待范围问题及实际状态恢复修复分别留档，最终采信 `.tmp/catalog-incremental-20261104/acceptance-summary.json` 及补验报告。父级查看最终首屏和已加载分类实际截图。
- 本次无迁移或新生产依赖。实际发布前已确认目标主站服务健康、schema 为 `0102_add_selected_web_games`，tracked 工作树干净；299 份既有未跟踪备份/原素材保留，不清理数据卷或旧目录。当前 API、worker、Web 镜像已固定回滚标签，恢复入口为服务器 `/data/releases/catalog-20261104-01a1a594/`，不是旧数据快照回写。
- 用户已明确授权 CDN → API → 前端。本次通过既有 CI/Deploy 按精确提交发布，须核对实际 plan 仅 backend/frontend；正常流程重建 API/worker 后再替换 Web，并 reload Nginx，不重建 Nginx/数据库/Redis或其他站点。若 plan 扩为全栈或服务不健康应停止，不借手动全栈 dispatch 强行继续。线上版本、分页、图片及懒加载验收以本次运行收据另行记录，不以本地或 CI 成功替代。

恢复时先回旧 Web，必要时再回旧 API/worker；保留旧 PNG、CDN 对象、旧镜像和本次源代码。回滚不删除新对象，不做全局缓存清理，不使用迁移备份覆盖现有数据库。

### 本批最终上线记录

- 实际应用版本为 `a07a8a73a50945ed3ecdccebb5544969c1f891b3`，供新版引用的 23 个 CDN 地址先行核对完成，再发布 API/worker，最后发布 Web。服务器 Web 镜像 revision 与该提交完全一致，API/Web 健康，Nginx、数据库、Redis 镜像保持发布前版本；网关仅 reload。没有新增迁移、改写旧数据、清理备份或全局清缓存。
- 首次 [CI 41809377044](https://github.com/ixiaoyy/ParallelLines/actions/runs/41809377044) 后端 Ruff、MySQL 迁移、633 项测试及 OpenAPI 通过，但前端被新增测试中的 6 个未使用参数拦住，因此整体 CI 失败且自动部署跳过。`c9eaa3c8` 已修正测试声明；后续提交未出现新的 CI 运行，原因未证实，不能把它记为云端验证通过。
- 生产验收另发现无优先名单的分页 SQL 被 MySQL 将绑定常量当成列序号，首次请求为 500。`a07a8a73` 只在无优先名单时省略该 ORDER BY 项，保留创建时间/ID与 CASE 排序、游标语义；离线回归先复现再通过，新增真实 MySQL 测试保留待 CI 执行。修复后的真实公开默认/CASE 首、次页四次 GET 均 200、无重复、游标推进，已对真实 MySQL 入口补验，未把 SQLite 检查当作生产证明。
- 在已有定向发布授权下，采用原 Dockerfile 和现有 SSH 通道从精确提交构建 API/worker；Web 从 `git archive` 的干净已跟踪源码构建一次，未将服务器未跟踪的旧数据库/证书备份送入构建上下文。不使用全栈手动 workflow，不改变流水线权限或取消既有完整性要求。最终原生镜像、健康与源码记录在服务器 `/data/releases/catalog-20261104-01a1a594/final-ready.json`。
- 线上桌面首次创建 33 张卡片、5 次目录请求，手机为 9 张、2 次请求；解压后的 JSON 正文分别为 33,953 / 16,721 字节，不代表压缩传输量或 LCP。默认发现页没有请求完整 `/catalog`，未加载分类没有游戏卡片；手机园林大图请求为零，滚动/横移后继续增加数据和图片。
- 14 个非空分类、229 款游戏已逐类到真实 EOF、逐款封面实际滚入视口核对；ID 唯一、数量与当前总数相符，封面最终均为 `200 image/*` 且自然尺寸非零。公开项目的 `my_score` 均为 `null`；真实服务端缓存 hit、ETag 条件请求 304、空正文和 `public, no-cache` 已通过。目录 API 的 CF 状态为 DYNAMIC，不能冒称已做边缘 JSON 命中。
- 一张旧封面首轮已收到 200 响应头但正文超过 25 秒限时；同 URL 无 cache-bust 定向复核完整 139,300 字节、耗时 2.39 秒且 CF HIT，随后所在分类逐款通过。保留首次超时及手机结束时取消屏外预取的原始记录，只补验受影响部分；不据本次成功宣称所有线路都没有 CDN 延迟。
- 最终综合页面清单为本地 `.tmp/catalog-incremental-20261104/online-a07a8a73a50945ed3ecdccebb5544969c1f891b3-summary.json`，真实 API 清单为 `.tmp/catalog-release-20261104/online-api-acceptance.json`；父级已查看电脑/手机实际截图。所有自有测试浏览器和一次性发布进程均已结束，生产服务与回滚入口保持可用。

## 构建缓存

- Web 的 pnpm、API 的 uv 下载缓存挂载只在同一持久 BuildKit 构建器内复用。GitHub Actions 的 `type=gha` 保存镜像构建层，不自动持久化 cache mount，不能据此宣称锁变化后仍命中下载缓存。
- API CI 使用 `astral-sh/setup-uv` 持久化下载缓存，按 Python 版本与 `uv.lock` 隔离。安装仍遵循锁文件，不缓存数据库、测试结果或运行时数据。
- Chat 提供显式、完整输入校验的前端产物缓存，旧无缓存入口保留。仅适合同一冻结输入再次交付；只构建一次或频繁改源码时使用旧入口。详见 Chat 仓库的 `docs/chat-frontend-build-cache.md`。
- Chat 历史本地命中完整命令为 10.364 秒且未运行 Vite；未命中总时间 179.617 秒，其中 Vite 140.264 秒、单独计量缓存额外成本 36.932 秒。未命中总时间不作为旧入口基线，不推算线上收益。

## CI 构建一次，部署消费同一产物

调用链为 `.github/workflows/ci.yml` → `.github/scripts/deploy_artifacts.py` → `apps/web/Dockerfile.prebuilt` → `.github/workflows/deploy.yml`。

1. CI 保存原 push 的 `before`、完整提交 ID、仓库、run ID 和部署范围。比较基线无法取得时按全范围处理，不猜单个父提交。
2. 前端 CI 用生产参数构建一次，将同次 `dist` 与 Nginx 配置封装为运行时镜像，不再次运行 Vite。源码 `Dockerfile` 仍可独立构建。
3. 自动部署只接受本仓 `main` 成功 push CI，拒绝 PR、失败或取消的 CI。只消费对应 run/SHA 的清单与归档；缺失、过期或损坏即停止，不换成其他产物或隐式重建。
4. 归档摘要、原始 config 摘要、平台、RootFS、revision、SHA 标签与服务端源码绑定同一提交；构建端 native 镜像 ID 单独保留审计，不能直接跨 Docker 存储类型比较。保留 `latest` 兼容现有 Compose。迟到旧 CI 跳过，已开始的部署不自动取消。
5. 后端或 Nginx 单独更新的正常路径不构建/下载 Web。Compose、全量、手动路径准备 Web；原缺服务 bootstrap 分支仍可能在服务器构建 Web。
6. 手动 `workflow_dispatch` 保留显式源码构建能力，不依赖历史 CI 产物。自动链省去重复 Vite，但仍有归档传输成本，实际端到端收益须实测。

自动范围只描述本次 push，不累计前一次 CI 失败后尚未发布的变化。修复推送通过后，发布负责方须检查前一批未上线的服务范围：可使用现有显式全量入口，或在同一已验证提交上补齐缺失服务。已由 CI 交付的 Web 镜像无需再次运行 Vite；不能把最后一次分流任务成功当成此前所有服务均已更新。

合同测试位于 `.github/scripts/test_deploy_artifacts.py`，只使用临时文件，不连接 Docker、GitHub 或服务器。
静态缓存条件另由 `.github/scripts/test_static_cache_contract.py` 核对，不用离线正则检查替代实际 Nginx 语法和响应头验收。

### 镜像身份：native ID 与 config 摘要

`web-image.json` 使用 schema 2。原 `image_id` 和 `.image-id` 旁文件仍是构建端原生 ID，不改含义；新增 `image_config_digest` 和 `.image-config-digest` 旁文件。该摘要从 `docker save` 归档中的原始 config bytes 计算，不从 `docker inspect .Config` 重建 JSON。清单同时保存 `image_revision`、`platform` 和有序 `rootfs_diff_ids`。

生产者不需要新增 Docker 操作：原 CI 和手动入口仍只构建、save 一次，由同一 `receipt` 命令生成新清单。`verify-web` 只接受 schema 2，并同时核归档 SHA、旁文件、两个 RepoTags 对同一个 config、原始 config 摘要、`linux/amd64`、revision 和 RootFS。当前不接受多镜像归档或多平台 index，不自动选取其他平台。

服务器收到同一清单的 SHA 命名副本 `.image.json`。归档校验和 load 后，先运行 `verify-loaded`，通过才替换服务：

```bash
sudo python3 -B .github/scripts/deploy_artifacts.py verify-loaded \
  --sha "$DEPLOY_REVISION" --receipt "$WEB_IMAGE_BASE.image.json" \
  --run-id "$SOURCE_RUN_ID" \
  --expected-config-digest "$(cat "$WEB_IMAGE_BASE.image-config-digest")"
```

- 两个标签必须指向同一 native 目标，且公开平台、RootFS 和 revision 一致并匹配清单。
- classic store 无 descriptor 时，native ID 必须等于 config 摘要，不要求安装或调用 `ctr`。
- containerd store 的 native ID 可为 manifest 摘要。核验器从 `docker info` 的 `Containerd.Address`、`Namespaces.Containers` 取得本机 endpoint，使用已有 `ctr content get` 只读两个小 blob。依次核 manifest 原始摘要/长度、config 描述符与原始摘要/长度，再核 config 平台、revision 和有序 RootFS 与 inspect/清单相同。标签、RepoDigest 或相同 revision 单独均不足以通过。
- 运行依赖为 Python 3.10+、Docker CLI；containerd 路径额外要求 daemon 所在主机已有 `ctr` 及内容存储读取权限。元数据命令各有 30 秒截止和 4 MiB 输出上限，config/manifest 大小预先受限。缺工具、权限、endpoint 或出现多平台歧义即失败，不安装、拉镜像或降级跳过。核验器不适合作为远端 `DOCKER_HOST` 的跨主机内容读取器。

### 已交付 schema 1 归档的显式恢复

旧 D51 CI 归档不因这次元数据修复而重建 Web。自动 `verify-web` 不接受旧 schema；操作员须先核对应 CI run、完整提交、原收据和归档 SHA/原旁文件，保留原证据，不能将 `.image-id` 自动解释成 config 摘要。然后使用已核验版本的新 helper 只读解析原归档：

```bash
python3 -B "$VERIFIED_HELPER" archive-identity \
  --archive /tmp/parallellines-web-d51b7fbbf8c4b9ba366c3c3bffb37cf0f6576d05.tar.gz \
  --sha d51b7fbbf8c4b9ba366c3c3bffb37cf0f6576d05
```

该归档原始 config 的已核摘要为 `sha256:87d4dc4f3e913c0993ea4ea766a2f312ed1cc3924f742bcc5f390c2bbeb77f5f`。确认解析结果后，操作员才可显式核已加载镜像：

```bash
sudo python3 -B "$VERIFIED_HELPER" verify-loaded \
  --sha d51b7fbbf8c4b9ba366c3c3bffb37cf0f6576d05 \
  --expected-config-digest sha256:87d4dc4f3e913c0993ea4ea766a2f312ed1cc3924f742bcc5f390c2bbeb77f5f
```

此入口输出 `mode=explicit_operator_config_digest`，不读取/改写旧收据，不代替原归档来源证明，也不自动部署。已加载 manifest 原生 ID 为 `sha256:79ecc680ddaf0ac28490a1282122ba5f278ffef8f3fa01d917fc3d66d9b9543f` 与构建端 `87d4…` 不同，并不构成身份变更；必须以完整原始内容链证明，不能移除校验或只信 revision。正常 schema 2 路径继续使用清单/来源 run 双重约束。

Docker 29.9 当前实现会把 containerd target digest 返回为 inspect ID，见 [Moby 对应版本实现](https://github.com/moby/moby/blob/a5b58c9/daemon/containerd/image_inspect.go)。containerd endpoint/namespace 由 Docker 管理，不硬编码默认值，也不通过 `ctr` 修改状态，见 [Docker 官方说明](https://docs.docker.com/engine/daemon/embedded-containerd/)。

本次元数据修复的 29 项离线合同通过，包含真实小型 save tar、原始 bytes 摘要、跨存储正例及别名/平台/revision/RootFS/损坏内容等负例。新 helper 对既有 D51 归档的只读解析，以及 Docker 29.9/containerd 已加载镜像的只读内容链核验均通过；实际 Python 为 3.12.3。classic 分支只做离线 fixture 验证。这些证据不等于已替换 Web 或完成页面/健康验收，实际部署由发布记录另行确认。

## Chat 与模型 API 的独立边界

- Chat 私有 source map 与公开资源分离，启动读取有可取消的截止和显式重试，设置弹窗按需加载。保持现有登录、模型与后端行为。纯前端部署只能更换 Chat 服务的镜像/构建配置，不连带更新身份桥、环境变量、挂载或网络配置。
- 模型 API 的冲突检查由完整计数改为同谓词 `SELECT id ... LIMIT 1`，锁、事务、角色、缓存恢复和计费保持不变。合成早命中可提前结束，正常无冲突未测出稳定收益，不宣传普遍登录提速。
- 模型 API 的正式发布源码、前端资产清单与镜像版本由其独立发布配方绑定，不能用旧发布脚本顺带改变免费/付费开关。

## 发布、验收与清理

- 发布前确认实际生产目标、当前镜像、Compose 挂载、未提交热修复及对应源码，保护当前和至少上一可用回滚版本。尤其不能用旧工作区覆盖最新主分支或线上身份热修复。
- 本流程不再自动执行全局 `docker image prune`。删除与部署分开：先只读盘点，再确认具体可删清单。保护数据卷、上传、备份、日志、密钥、证书、其他服务、回滚镜像和对应源码；有价值的构建缓存不盲目清空。
- SHA 镜像标签不是完整自动回滚能力。实际发布还须记录健康检查、恢复方式、线上页面/图片自然尺寸和响应类型，以及缓存响应头。
- 本地类型检查、构建和隔离浏览器结果不代表线上 LCP、CDN 命中率、真实首字延迟、手机帧率或构建缓存命中。Docker/GitHub Actions/目标服务器的实际结果以发布记录为准。
