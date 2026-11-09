# 独立工具站运维入口

已实现 `inventory`、`health` 及显式写阶段 `prepare-tls`、`deploy`、`rollback`。用户已确认目标为现有主站生产主机，工具应用独立放在 `/opt/parallellines-tools`，域名为 `tools.pingxingxian.space`。push 只读，写操作须由 root 按本次授权显式 dispatch；代码和本地替身测试完成不代表生产部署通过。

## Inventory 如何触发

- 仅本仓库 `ixiaoyy/ParallelLines` 的 `ops/tools-deploy-20261109` 分支 push，且本 workflow/本目录有改动时触发。
- push 始终只执行 `inventory`。`workflow_dispatch` 只能选择该明确分支及上述五个操作。main、其他分支及 PR 均不获得此 job。
- 使用原有 `DEPLOY_*` Secrets 和原主机指纹，经现有 SSH Action 执行只读脚本。密钥只作为 Action 正常认证输入，不写脚本、日志或运维文档。
- workflow 将本提交已审核的公开 ops 源码装配后，通过 SSH 标准输入交给 `sudo -n python3 -B - <operation>`；不执行发行包内程序，不写 Python 字节码。deploy 会在自有目录保留独立恢复和续期入口；其他操作不留下临时执行文件。完整 SSH payload 上限 120000 UTF-8 字节。
- SSH Action 禁用 `script_stop` 逐行注入，避免破坏 Python heredoc；payload 自身以 `set -eu` 开始，末条 Python 命令的失败状态直接作为远端 shell 的退出状态，不伪装成功。
- 本阶段 root 负责分支、提交、推送和读取现场回执；本目录的编写者不自行连接生产。

`ci.yml` 目前仅 push main 或 PR 执行；`deploy.yml` 自动接收的是 main 的成功 CI。因此本运维 feature 分支的普通 push 不会触发旧主站发布。不要为了启动 inventory 手动点击旧 Deploy workflow。

现场已经证明本分支的显式 `gh workflow run --ref` 可用，不再需要为了注册 dispatcher 复制一份 workflow 到 main。

## 已确认现场与未知项

现场回执 `42508258911` 确认 gateway 为 `parallellines-nginx-1`，可复用网络为 `parallellines_default`，另两个既有网络不变；Certbot 为 `parallellines-certbot-1`、5.8.0，证书目录与 ACME webroot 对应现有 bind mounts。主站配置 tracked/clean。

回执中 Git HEAD、SHA256 和部分 Docker ID 含 GitHub 自动屏蔽字符，属于未知数据，禁止猜测、拼回或解码。写阶段必须使用 root 从已知完整本地前像取得的 SHA256，在远端直接比较，只输出 `expectedPreimage` 布尔值。

## Prepare TLS

显式调用（仅由 root 执行）：

```text
gh workflow run tools-ops.yml --ref ops/tools-deploy-20261109 -f operation=prepare-tls -f expected_config_sha256=<已知完整本地前像的64位SHA256>
```

顺序：

1. 检查主站配置前像、该文件 Git clean 状态、固定容器/挂载/网络和 Certbot 版本。
2. 只读确认现有 cron 调度能力；不可用时停在写入之前，不先获取一次性无法运维的证书。
3. 在独立工具 release 目录备份已匹配的 Nginx 前像，权限 0600；不复制任何旧账户或私钥。
4. 在固定 webroot 排他创建随机 HTTP01 探针，公网真实 GET 必须匹配内容；仅允许最多三次同域 HTTP/HTTPS 跳转，完整探针限 22 秒。无论结果如何，只清理本次拥有的探针文件。
5. 再次比较前像后，才在现有官方 Certbot 容器内申请工具域名证书。客户端进程自身限 300 秒，日志备份数量为 2，不强制重复签发。
6. 验证新公共证书只有工具域名且有效期超过 30 天。此阶段不安装 vhost、不 reload gateway，续期消费者安装与真实 dry-run 仍待部署阶段验收。

专属正常 Certbot 配置目录为容器内 `/etc/letsencrypt/parallellines-tools`，对应宿主机 `/opt/parallellines/var/letsencrypt/parallellines-tools`。未来工具 vhost 应引用该子目录的 `live/tools.pingxingxian.space/`；不能使用父目录旧证书或手动复制 key。

工具账户、CSR、证书和密钥均由官方 Certbot 正常创建和管理；无已知邮箱时明确无邮箱注册，不伪造联系邮箱。工具操作同时指定隔离 config/work/log 目录、`--config /dev/null`、`--no-directory-hooks` 和空的 pre/post/deploy hooks，不调用旧全局目录 hooks 或旧 ACME 账户。

Certbot 5.8 的持久续期参数不包含 `directory_hooks`；不能把首次传 `--no-directory-hooks` 当成既有父目录全局 renew 循环也会跳过旧 hooks 的证据。独立子目录避免父目录 `renewal/*.conf` 自动扫描工具配置。依据：[Certbot 5.8 renewal 参数](https://github.com/certbot/certbot/blob/v5.8.0/certbot/src/certbot/_internal/renewal.py)、[hooks 调用边界](https://github.com/certbot/certbot/blob/v5.8.0/certbot/src/certbot/_internal/hooks.py)。

`tls.py renew`、`tls.py renew-check` 和 `tls.py scheduled-renew` 不由 workflow push 或默认 dispatch 调用。deploy 将 ops 和专属 cron 源保存在 `/opt/parallellines-tools`，仅安装本任务拥有的新调度入口，不改旧 cron/cert/hooks。续期只选工具 cert-name，关闭随机延迟和旧 hooks；配置整体 clean 或仅含已记录的工具标记段才允许 reload。新公共证书先记 pending；只有 `nginx -t`、reload 和源站 SNI 证书身份确认均成功才记 loaded 并清 pending。即使本轮文件未再变化，也会重试上次未完成的加载；无 pending 且无变化不 reload。消费者只保留一份有界最新结果，失败不写成 complete。真实 dry-run 和已安装消费者成功前不宣称续期闭环通过。

## 独立只读 Health

`operation=health` 不与写阶段共用并发队列，因此写阶段长命令失败时仍可另行检查。脚本也能在部署后以独立文件运行，不依赖之前的执行进程。

检查固定 12 项：gateway 容器与 `nginx -t`、本机 `/nginx-health` 原有 204、工具来源/镜像/网络与容器内 healthz、直接连接环回 443 的工具 SNI/标准 CA、工具公网 healthz/首页标题，以及主站、Chat、OIDC、New API 的固定公开健康入口。每项最多 6 秒、总计 70 秒，无重试、不跟随跳转，不输出正文或原始 stderr。工具尚未部署时返回失败是正确负结果，不当作工具容器已经健康。

## 输出与限制

输出为 SSH job 日志中的 JSON，包含：

- 容器名称、固定筛选的镜像/状态/Compose service/project 标签及网络名称，不查询 Env 或完整 labels。
- 根据实际 `/opt/parallellines/deploy/nginx/default.conf` bind mount 识别的唯一 gateway，及其配置/证书/ACME 挂载与网络。
- `nginx -T` 输出的白名单摘要：include、公开 server_name/listen、root、公共证书路径和 ACME location。不会输出完整配置、请求头、私钥路径或原始 stderr。
- `/opt/parallellines` 当前 Git HEAD；仅 `deploy/nginx/default.conf` 的 tracked/dirty 布尔值及 SHA256。Git 禁用可选锁及 fsmonitor，不读其他改动、不 fetch、不 checkout。
- 指定目录的磁盘容量、系统负载；公共证书 SAN/到期时间、续期配置路径、hook 目录与 certbot 工具版本。不读取续期账户文件、私钥、DNS 凭据或真实 `.env`。
- 通过 Google 公共 DNS-over-HTTPS 查询 apex/tools 的 A/AAAA，固定四次请求、有超时和响应上限、不重试。CDN IP 不等于源站 IP；解析存在不证明 ACME 路径可达。

公共 JSON schema 使用 `certificate_store` 表示证书目录，使用 `document_directory` 表示 Nginx 的静态文档目录指令。只调整固定的非秘密字段名，不编码、还原或解码 GitHub 已屏蔽的实际值；源站路径和域名仍按原值正常输出并接受平台脱敏。

容器上限 64、gateway 候选上限 8、公共证书上限 12；子命令和 SSH 均设时限。异常仅输出稳定错误码，`complete=false` 时以非零退出，不把部分信息当作完整验收。不得通过扩大读取范围、打印 secrets 或改服务器来处理 inventory 失败。

本地测试为 `python -m unittest discover -s deploy/tools -p 'test_*.py'`，使用 Python 标准库和替身，不访问生产或 DNS。新增部署用例覆盖真实 writer 部分追加恢复、gateway ID/bind/inode 漂移零突变、同 SHA 后继 attempt 保护；续期覆盖失败后第二轮补加载。这些结果不替代实际 SSH、Docker、HTTP/TLS、Certbot 或生产恢复验收。

## 部署持久化边界

已授权的 deploy 阶段遵循：

1. 在 `/opt/parallellines-tools` 使用独立 Compose project、独立静态镜像/容器及固定版本，不复用主站 Web/数据库/数据卷，不争用宿主机的 80/443。接入现场确认的 gateway 可达网络，不能把容器内的 `127.0.0.1` 当作宿主机环回。
2. 工具子域独立 server 段应持久进入主站仓库 tracked 的 `deploy/nginx/default.conf`，只新增工具域名段，保留原有主站、Chat/OIDC、New API、Fable 配置。root 管理这一共享文件。仅 `docker cp` 到容器层或在服务器未跟踪地追加配置都会被后续重建/更新覆盖，不作为交付。
3. 现有配置只 bind 了 `default.conf` 文件；在没有新 mount 的情况下，不能假定另建 host 文件会自动进入容器，也不能依赖尚未存在的 include 目录。是否增加 include/mount 应依据 inventory 后另行决定，不在本阶段改 Compose 或重建 gateway。
4. 默认 CI 的正常可比较 main push：`deploy/nginx/**` 只置 `nginx=true`，Compose 仅匹配根 `docker-compose.yml` 和 `deploy/docker-compose.migration.yml`；缺 before 或取不到比较基线则会按 FULL 处理，不能只凭文件名假定范围。
5. **现有 nginx-only 发布不是 reload-only**：它会 `--force-recreate nginx`，且 nginx 未运行时 fallback 全栈 bootstrap。本次限定为必要 reload，因此不能直接触发现有 nginx-only 或 manual full-stack。root 决定持久提交与独立 tools-ops 受控发布的时序；不得由本脚本自动触发旧工作流。

## 备份、健康检查和恢复路线（deploy 前必须具备）

- 将 gateway 当前配置、其 Git HEAD/dirty/摘要、镜像身份、网络/挂载以及工具站旧版本记录在独立 release 目录。备份配置原文留在服务器受限权限下，不进入共享日志；不备份或展开私钥/真实 env。
- 修改前校验现场主站配置仍匹配 inventory 的 HEAD/dirty/摘要；如漂移，由 root 重新对齐增量，不整仓 checkout/reset，不覆盖其他更新。
- 新工具容器先独立 HTTP health 检查通过，再开放工具 vhost；ACME HTTP challenge 必须从公网验证实际路径，不能只凭 A 记录或 CDN 响应申请即视为成功。
- tools 使用独立证书名称和续期策略，不覆盖 apex/Chat/API 原证书；证书更新后的 reload 路径须明确。
- 备好独立于本次 SSH 长命令的健康入口：gateway 本机 `/nginx-health`、工具容器内 HTTP health，以及 apex/tools 的外部 HTTP/TLS 检查。后续实际执行前确认这些入口与实际容器匹配。
- 只应用选定工具增量配置，执行 `nginx -t` 成功后才 reload。失败不 reload，保留原服务；reload 后同时核验 tools、主站和原 Chat/OIDC/API 入口没有回归。
- 恢复只切回工具镜像/产物及本次工具增量配置，重新 `nginx -t` 后 reload；旧主站其余段落/数据卷不动。恢复命令和配置副本必须在执行前可独立使用，不能依赖失败中的部署进程。

## 显式部署与恢复

```text
gh workflow run tools-ops.yml --ref ops/tools-deploy-20261109 -f operation=deploy -f release_tag=site-<40位应用提交> -f receipt_sha256=<可信公开回执SHA256> -f expected_config_sha256=<可信本地配置前像SHA256>
gh workflow run tools-ops.yml --ref ops/tools-deploy-20261109 -f operation=health
gh workflow run tools-ops.yml --ref ops/tools-deploy-20261109 -f operation=rollback -f release_tag=site-<待撤销部署的40位应用提交>
```

deploy 先核 receipt、静态归档大小/摘要和安全路径，再核四份固定描述符：COPY-only Dockerfile、专用 dockerignore、Compose 和容器静态 Nginx 配置。仅允许从官方 Nginx digest 封装已验证 dist，不运行 npm/Vite/媒体编译。工具容器无 host ports、DB 或数据卷，只接入 `parallellines_default`，上限 CPU 0.5、内存 256 MiB、进程 64。

配置原文备份与完整事务保存于自有 release/attempt 目录。切服务前重核 gateway、RO bind、宿主/容器 inode 和配置前像；只原 inode 写入唯一工具标记段，`nginx -t` 后 reload，不 recreate gateway。工具及原站健康、独立证书 dry-run 和真正安装消费者都成功后才提交 current 状态。

rollback 撤销指定应用部署的工具增量，不是把任意旧标签直接发布。恢复前先核完整 attempt 与原 gateway/bind/inode；若已被其他部署接管或网关被替换，保留 pending 和备份并停止，不能向新实例补偿写入。首次追加被中断时，仅恢复由本事务原文和工具片段严格证明的 EOF 部分尾部，不接管外部字节。写操作与既有主站发布共用 `deploy-production` 并发组；health/inventory 独立，执行通道失败后仍可使用。
