# 性能优化与发布边界

## 范围

本批覆盖主站、工作区内的游戏与工具，以及相邻 Chat、模型 API 仓库。不包含 Fable 独立站、身份/计费规则变更、发布排空、维护门或新增 `503`。本文件描述实现和本地证据；提交、推送、实际部署与线上验收须分别记录。

## 页面与资源

- 游戏目录只让推荐首组或筛选结果的前三张封面立即加载，其中第一张设高优先级；后续分类仍懒加载。保留当前玉青目录、筛选、投稿及 AI 评分展示。
- Vite 根据实际 `VITE_STATIC_ASSET_BASE_URL` 为 HTTP(S) 静态域名生成 `preconnect`，相对路径不额外预连。已有 CDN 配置继续有效；这不代表 CDN 已命中。
- 新游戏图片和分类图集使用无损 WebP，原 PNG 保留，尺寸和 RGBA 内容相同。新增图片引用仍为同源路径，不指向尚未上传的 CDN 文件。后续切换 CDN 时，先上传并验证公开地址，再切引用。
- Web Nginx 压缩文本资源。指纹 `/assets/` 使用一年不可变缓存；限定目录内非指纹公开图片使用一天缓存和后台重新验证。HTML、接口、上传资源不扩大缓存范围。
- 主站共享 Nginx 对 Chat、模型 API 只允许状态成功、类型明确的指纹资源长缓存，其余响应保持 `no-store`；不能用 CDN 全站缓存覆盖登录、个性接口或生成流。实测 Chat 缺失静态文件会回退为 `200 text/html`，因此不能只按 `/_app/immutable/` 前缀缓存。API 对应配置也保留在独立仓库的 vhost 模板中。
- 拼豆画布复用底图，缩放和聚焦不再重绘底图或重置缓冲；生成规则与导出保持不变。
- 回廊第 4 关只缓存固定装饰、复用实例缓冲，保留最新主分支的角色、门、支撑和移动子步修复。旧开发基线的 Float32 分配和耗时数据不能代替新组合或线上帧率；新主分支组合的冻结状态画面、GPU 数据和关卡状态等价检查单独留证。
- 主站 SEO 链接读取改为只查询所需字段，省去页面不使用的评分聚合；真实目录接口保留用户评分和 AI 汇总。

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
