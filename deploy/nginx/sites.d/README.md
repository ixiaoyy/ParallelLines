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
