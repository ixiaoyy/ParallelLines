# 共享 Nginx 网关站点路由目录归属说明

依据全站系统架构总纲 `ARCHITECTURE.md`（2026-11-19）：

1. **统一配置归属与发布入口**：共享边缘网关的最终配置与发布入口由 `ParallelLines` 持有。各子站点可以维护各自的路由文件，但必须经由**同一条发布链**完成加载、`nginx -t` 校验与切换。
2. **优先持久化容器层站点，不搬动已持久化站点**：
   - 使用 [docker-compose.gateway-sites.yml](../../docker-compose.gateway-sites.yml) 挂载引导文件 `00-include-sites.conf`（映射到 `/etc/nginx/conf.d/zz-gateway-sites.conf`）与宿主机持久化目录 `/opt/parallellines/nginx/sites.d`（只读挂载到容器内 `/etc/nginx/sites.d`），无需改动现有 `default.conf`。
   - **优先动作**：先把当前依赖容器层的 `tavern.pingxingxian.space` / `matrix.pingxingxian.space` 路由文件纳入该持久化目录，避免共享网关容器 `recreate` 后丢失入口。
   - **克制原则**：已经通过既有机制持久化的站点不要为了目录整齐强行搬一遍。
3. **故障域清醒认知**：
   - 分文件解决的是**配置归属与可维护性**，**共享网关的故障范围并不会因此缩小**。
   - 任何站点配置更新都必须先经同一发布链执行 `nginx -t` 校验并保留回退前像，避免单个配置语法错误影响全部共享站点。

## 主站发布与初签重载互斥

- 主站全栈、API、前端和 Nginx 四条 Deploy 写入口复用 Tools 的 `/opt/parallellines-tools/ops/tls.lock`。先获取提交，再取非阻塞独占锁，从重置实际挂载源到 Compose 切换、初签分支（如触发）和写成功回执保持同一次锁。取代码和 runner 上传不占锁；重置后的原构建仍在锁内，不把持锁期间的未完成工作树暴露给其他续载操作。运行身份仍是原部署账号。
- 锁已占用时发布入口立即以状态 `75` 停止，未重置工作树或更新服务，待原操作完成后重新派发。缺锁、非受控文件或同一路径的 inode 已改变时拒绝发布；不要另建、替换或删除锁。宿主入口只接受 64 KiB 以内的固定工作流脚本，现有四条都在范围内。
- 正式 Compose 只读挂载同一文件，Nginx 镜像使用 Alpine 的 `flock`。容器首次切正式证书时在锁内重查两条链接并用 `nginx -t` 验证后重载；争锁最多等到下一轮 60 秒轮询后再试，失败保留原链接。Nginx 的正常启动不等这把锁，基础 Compose 的本地入口不依赖它。容器未重建前，旧镜像不会获得新守卫。
- **未改定时续期**：主站 Certbot 每 12 小时的原生 `renew` 与现场钩子继续原样工作。部署上线前先核实际锁文件、部署账号权限、网关挂载和续载消费者的实例锚点；如需执行初签分支或给定时续期本身加锁，先确认现场 Certbot 钩子不会再次请求同一锁。未核前不关闭钩子、不另设调度，不把本变更当作网关重建或证书已完成线上验收。

## 重建前检查与失败处理

1. **先看现场，不重建。** 获准只读核对后，用现有酒馆 `inventory`、`health`、`renewal-status` 和圈子 `inventory`、`health` 确认当前网关、实际挂载和续载锚点。重点区分哪些路由来自宿主机挂载、哪些只在旧容器层；不把仓库模板或启用标记当作现场证据。
2. **没有可用恢复入口就不重建。** Tavern/Matrix 和圈子路由必须在目标挂载中各有唯一归属，现有发布、撤回和续期必须已匹配目标位置与容器。保留已核对的配置前像、原镜像和恢复步骤；先对候选验证 `nginx -t` 与跨配置的路由归属，再在同一 TLS 锁下执行当次获准的切换。拿到锁不等于满足重建条件。
3. **重建后先核消费者。** 分别核主站、圈子、Tools、Chat、API 和 Tavern/Matrix 的真实入口，以及证书续载消费者能识别新网关。酒馆内部健康不能代替公网入口检查，另确认 `public_entry=true`。任一异常停止后续动作，保留证据并使用已核的对应恢复入口。不直接重跑整站 Deploy，不为了复测故意触发证书签发或停用续期。

### Tavern / Matrix 切换条件与受控迁移链路（代码已收口，待生产获准切换）

- **迁移的是同一份路由（统一持久读写）。** 以当前 `public-entry.json` 登记的配置摘要核对运行层和独立恢复源；不复制第二份模板长期维护。`publish`、`retract`、失败恢复与续期检查统一读写宿主机 `/opt/parallellines/nginx/sites.d/parallellines-entertainment.conf`，在同一 `/opt/parallellines-tools/ops/tls.lock` 下执行原子替换。当网关容器已启用 `docker-compose.gateway-sites.yml` 只读挂载（`/etc/nginx/sites.d` 与 `/etc/nginx/conf.d/zz-gateway-sites.conf`）时，仅更新宿主机文件并 `nginx -s reload`，绝不往只读挂载执行 `docker cp`，并拒绝容器层 `/etc/nginx/conf.d/parallellines-entertainment.conf` 与持久层并存两份路由。
- **发布和撤回分别验收。** 发布态通过 `verify-gateway-sites.mjs --require-active-routes --require-route parallellines-entertainment.conf=tavern.pingxingxian.space,matrix.pingxingxian.space` 强制校验两个域名的全部 `server_name` 唯一归属目标文件，并写入 `.deployment/gateway-sites-enabled` 供 `select_compose_files.sh` 接续；仅有其他站点或目录非空不会放行。主动 `retract` 撤回最后一个站点时，自动移除 `.deployment/gateway-sites-enabled` 标记（若目录内仍有其他合法站点则仅移除 Tavern/Matrix 路由契约行、保留其他站点挂载）；验证或 reload 失败时自动回滚宿主机文件、容器层（若未切挂载）与启用标记前像。
- **程序与回执整组前像迁移。** `install-renewal` 升级已装 `operations.py` 与 `renewal.json` 前，先将旧版程序与回执排他备份至 `runtime/operations.before-persistent-sites-1abefac5.py` 及对应 JSON，并通过独立子进程 `health` 探针验证后才结案，异常自动还原整组前像。`enable-main-login` / `restore-main-login` 升级 `sso-operations.py` 与 `main-login.json` 时，同步将关联的 `runtime/element-background-v1/transition.json` 与 `runtime/tavern-invite-module-v1/transition.json` 的 `program_sha256` 纳入同一事务备份与原子切换，避免定时任务或角色回退读到半套新旧文件。
- **生产切换与删除兼容分流步骤。**
  1. 在当前网关未重建前，依次执行 `publish`（落盘宿主机 `sites.d/parallellines-entertainment.conf` 与 `.deployment/gateway-sites-enabled`）、`install-renewal`（原子升级 `operations.py` 与 `renewal.json`）、`enable-main-login`（幂等原子升级 `sso-operations.py`、`main-login.json` 及关联 transition 回执）、`renew`（完成 native 续期校验并使 `renewal-status` 报告 `renewal_ready=true, last_run_complete=true`）。
  2. 回退前像核验通过后，执行另行授权的共享 Nginx 重建（加载 `docker-compose.gateway-sites.yml` 只读挂载，移除旧容器层临时文件），再次执行 `renew` / `renewal-status` 与 `health` 登记新网关容器身份，核对挂载、路由唯一归属、两域 JSON、其他站点和续期状态。不重建 Element、Synapse 或数据库，不强制换证。
  3. 本地工作流 `entertainment-ops.yml` 已移除六个动作读取旧提交 `1abefac5` 的临时兼容分流分支，统一使用当前已审源码。
