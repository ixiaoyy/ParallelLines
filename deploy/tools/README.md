# 独立工具站运维入口

当前阶段只实现 `operation=inventory`。用户已确认目标为现有主站生产主机，工具应用独立放在 `/opt/parallellines-tools`，域名为 `tools.pingxingxian.space`。当前入口不部署、不上传、不申请证书、不修改 Docker、Git、Nginx 或 DNS。

## Inventory 如何触发

- 仅本仓库 `ixiaoyy/ParallelLines` 的 `ops/tools-deploy-20261109` 分支 push，且本 workflow/本目录有改动时触发。
- `workflow_dispatch` 同样只能选择该明确分支和唯一的 `inventory` 操作。main、其他分支及 PR 均不获得此 job。
- 使用原有 `DEPLOY_*` Secrets 和原主机指纹，经现有 SSH Action 执行只读脚本。密钥只作为 Action 正常认证输入，不写脚本、日志或运维文档。
- workflow 将当前提交的唯一脚本通过 SSH 标准输入交给 `sudo -n python3 -B - inventory`；不在生产下载脚本，不写 Python 字节码，也不留下临时脚本文件。
- 本阶段 root 负责分支、提交、推送和读取现场回执；本目录的编写者不自行连接生产。

`ci.yml` 目前仅 push main 或 PR 执行；`deploy.yml` 自动接收的是 main 的成功 CI。因此本运维 feature 分支的普通 push 不会触发旧主站发布。不要为了启动 inventory 手动点击旧 Deploy workflow。

## 输出与限制

输出为 SSH job 日志中的 JSON，包含：

- 容器名称、固定筛选的镜像/状态/Compose service/project 标签及网络名称，不查询 Env 或完整 labels。
- 根据实际 `/opt/parallellines/deploy/nginx/default.conf` bind mount 识别的唯一 gateway，及其配置/证书/ACME 挂载与网络。
- `nginx -T` 输出的白名单摘要：include、公开 server_name/listen、root、公共证书路径和 ACME location。不会输出完整配置、请求头、私钥路径或原始 stderr。
- `/opt/parallellines` 当前 Git HEAD；仅 `deploy/nginx/default.conf` 的 tracked/dirty 布尔值及 SHA256。Git 禁用可选锁及 fsmonitor，不读其他改动、不 fetch、不 checkout。
- 指定目录的磁盘容量、系统负载；公共证书 SAN/到期时间、续期配置路径、hook 目录与 certbot 工具版本。不读取续期账户文件、私钥、DNS 凭据或真实 `.env`。
- 通过 Google 公共 DNS-over-HTTPS 查询 apex/tools 的 A/AAAA，固定四次请求、有超时和响应上限、不重试。CDN IP 不等于源站 IP；解析存在不证明 ACME 路径可达。

容器上限 64、gateway 候选上限 8、公共证书上限 12；子命令和 SSH 均设时限。异常仅输出稳定错误码，`complete=false` 时以非零退出，不把部分信息当作完整验收。不得通过扩大读取范围、打印 secrets 或改服务器来处理 inventory 失败。

本地检查仅运行 `python -m unittest discover -s deploy/tools -p test_inventory.py`，全部依赖为 Python 标准库，使用替身，不访问生产或 DNS。

## 后续部署的持久化方案（尚未实施）

现场 inventory 回执确认后，由 root 单独批准并实施 deploy 阶段：

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

当前没有 deploy job。增加 deploy/reload/证书操作前，必须由 root 根据现场回执再次明确批准脚本范围。
