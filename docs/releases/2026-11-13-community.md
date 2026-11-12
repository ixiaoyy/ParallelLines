# 圈子拆分与四产品导航生产回执

日期：2026-11-13（北京时间）。本次用户明确授权提交、推送和生产部署，以下只记录实际完成范围。

## 结果与版本

- [游戏主站](https://pingxingxian.space/)、[圈子](https://forum.pingxingxian.space/)、[工具站](https://tools.pingxingxian.space/)、[聊天入口](https://chat.pingxingxian.space/)均可访问。导航统一为 `游戏｜圈子｜工具｜聊天`，当前标签打开。
- 主站及圈子应用源码：[93ca819f20f760b142cab9a320110879ff8179df](https://github.com/ixiaoyy/ParallelLines/commit/93ca819f20f760b142cab9a320110879ff8179df)。主站 `main` 上随后另有本次受限运维入口、恢复及验证接线提交；应用候选始终固定为此版本，没有用帮助脚本提交冒充应用重建版本。
- 工具源码：[869cf54e2ea9aada678ef124e9ce9714f329fb05](https://github.com/ixiaoyy/parallel-lines-tools/commit/869cf54e2ea9aada678ef124e9ce9714f329fb05)，已推送原 `feat/pingxingxian-toolbox` 分支。仅包含本次页脚、译文及直接测试，保留工作区其他改动。
- 运维分支的主站重复发布保护修复：[40fda5ef2c89991cc015ad8d6d34b5013f1bcb7b](https://github.com/ixiaoyy/ParallelLines/commit/40fda5ef2c89991cc015ad8d6d34b5013f1bcb7b)。已迁移的工具入口不再被误反向恢复；混合、重复或未知前像仍拒绝。

## 实际发布与验收

| 阶段 | 实际证据 |
| --- | --- |
| 主站干净源码镜像 | [构建 43250960005](https://github.com/ixiaoyy/ParallelLines/actions/runs/43250960005)、[固定 Release](https://github.com/ixiaoyy/ParallelLines/releases/tag/main-web-93ca819f20f760b142cab9a320110879ff8179df)；使用 schema 2 回执和精确生产者 run ID |
| 圈子候选准备 | [43257882340](https://github.com/ixiaoyy/ParallelLines/actions/runs/43257882340)；独立公开源码副本构建前端，Node 堆上限 1536MiB；API 在已核旧镜像上仅 COPY 四个变更文件，不重装依赖 |
| 新域名 HTTP01 与证书 | [探针 43260840508](https://github.com/ixiaoyy/ParallelLines/actions/runs/43260840508)、[证书 43261462285](https://github.com/ixiaoyy/ParallelLines/actions/runs/43261462285)；唯一探针正文回读 HTTP200，未绕过 TLS，未改旧证书/hooks |
| 圈子实际启用 | [43264179071](https://github.com/ixiaoyy/ParallelLines/actions/runs/43264179071)；完整回执成功，网关未重建，API/论坛之外服务身份保持，七项公网/源站健康通过 |
| 主站前端实际更新 | [43265035310](https://github.com/ixiaoyy/ParallelLines/actions/runs/43265035310)；[独立盘点 43265730806](https://github.com/ixiaoyy/ParallelLines/actions/runs/43265730806)确认实际运行精确应用镜像，不能只用 Actions 绿色状态代替运行验收 |
| 工具干净源码与容器验收 | [构建 43250590099](https://github.com/ixiaoyy/parallel-lines-tools/actions/runs/43250590099)、[固定 Release](https://github.com/ixiaoyy/parallel-lines-tools/releases/tag/site-869cf54e2ea9aada678ef124e9ce9714f329fb05)；实际 Docker/Nginx/静态 HTTP 合同通过 |
| 工具实际更新 | [43266261806](https://github.com/ixiaoyy/ParallelLines/actions/runs/43266261806)、[独立健康 43266757523](https://github.com/ixiaoyy/ParallelLines/actions/runs/43266757523)；12/12 健康通过，实际入口 JS 与 Release 字节相符 |
| 最后续载消费者检查 | [43268377982](https://github.com/ixiaoyy/ParallelLines/actions/runs/43268377982)；主站及工具切换后真实执行固定 `check`，成功且 `reloaded=false`，只更新自身检查报告 |
| 最后源站盘点 | [43268389042](https://github.com/ixiaoyy/ParallelLines/actions/runs/43268389042)；应用工作树 `main` 位于 93ca819f 且 tracked/index clean，数据库版本仍为 `0110_add_six_featured_games` |

圈子实际 API 镜像 ID 为 `sha256:4f2e43c0ee4a95c93734b075be7860cf2e4ce1407c1603f8f8689a309e4e00ea`，圈子静态镜像为 `sha256:581718a121c5bfd02e63b18da570142b3f358528fbb6b4e0313691f297a30f46`。主站实际 native image ID 为 `sha256:db4c12e1ce357f6ec3b63eff368fe0ff46697835c2f4975e1d0b12f66528ffc6`，与生产者回执的 config identity 分开记录，按既有 schema 2 合同核验。工具实际 image ID 为 `sha256:921c90f3e4653f7e5ba5197df3fe23d4dcfcc84e47940d3e45342f1252a8ba44`。

日志被遮蔽的字段保持未知，未猜补、编码搬运或换通道恢复。授权只使用已独立核实的公开任务身份，完整运行状态仍在服务端作并发守卫。最终盘点日志中一个被遮蔽的资源数值在本地阅读副本中标为未知，不据此推断资源结果。

## 页面与业务边界

- 原论坛首页、公开版块、主题正文和匿名发布主题的登录回跳实际可用，圈子 title/canonical 均为新域；没有重做或清空论坛。
- 主站顶栏/页脚、圈子页脚、工具中英文页脚实际四项正确；主站真实点击圈子和 Chat 在同一标签到达。主站和圈子 1440/390/320px、工具 1280/390/320px 截图已实际查看，没有横向溢出或控件遮挡，导航至少 44×44px。
- 旧主域 `/forum`、`/boards` 和已存在主题路径使用真实 HEAD 验证为 302，查询串原样保留。片段延续沿浏览器规范和已有客户端回归；没有为重验旧主题再触发详情业务。
- 没有创建测试账号、发帖、回复、评分或修改正文；未使用真实账号登录。自动统计 POST 已拦截。**主题详情 GET 自身会按既有逻辑计数，浏览验收可能增加主题浏览量/热度；未查询或回改这些计数。**
- 本次没有新增数据库迁移、复制账号或帖子、改真实 `.env`、变更 Chat/OIDC/模型网关身份或计费配置。新域使用原账号，但浏览器来源不同，需要重新登录；不含跨子域免登录。

## 当前运行与恢复

- 网关保持原容器 `7aef40bb…`，宿主配置仍为 device `64769`、inode `1049133`；主配置与公开 APP93ca Git blob 一致。没有整体重建网关、移除网络或清理旧镜像。
- 首次热接入把两份精确已审论坛配置放入现有网关容器层，默认配置同 inode 更新。容器普通重启保留该层；将来重建容器必须用论坛 Compose 挂载接续配置，同时先接续工具、主站发布及圈子续载消费者的实例/配置锚点，不能直接 `--force-recreate nginx`。
- `.deployment/forum-enabled` 为 `community-93ca819f20f760b142cab9a320110879ff8179df`。API/论坛首次接线与恢复快照位于 `/opt/parallellines/.deployment/community/93ca819f20f760b142cab9a320110879ff8179df/`；状态、旧文件和旧镜像均保留。
- 圈子六小时证书续载消费者独立安装，仅比较本域公共证书与标准 CA/SNI；变化时经所有权、锁与 `nginx -t` 后才 reload。旧工具 cron、旧证书/hooks 保留。当前真实 `check` 已过，自然续期/自然 cron 到期尚未发生。
- 本次固定应用的独立 `community-ops.yml` 提供 `health`、`check-renewal` 与 `rollback`，写操作使用全局发布并发组。恢复只接受本事务精确前像，遇外部源/实例/配置漂移明确停止，不强制覆盖。
- 需要整批恢复时先停止竞争发布，按工具静态版本、主站 Web、圈子/API 的逆序协调，使用各自保存的旧 image 与事务回执；圈子恢复不清空数据/证书。不得 `down -v`、全树 reset、全局 prune 或恢复旧数据库覆盖新用户数据。

## 尚未执行及责任

- 真实账号登录后的发帖、私信、上传和后台权限路径未在生产写验收；本地替身证据不冒充真实写入。由账号使用者在新域重新登录后确认，禁止把密码/令牌发到聊天。
- 真人手机操作、证书自然续期及后续完整自动网关重建链未代签；后续发布负责人须按当前实际状态重新核实例锚点、挂载和消费者后再操作。
- 工具 React Doctor 本机未安装，因此未执行或临时安装；定向浏览器/ESLint、干净发布构建和真实容器验收已完成，但不称它们等价于该诊断。

本次没有安排额外付费服务、全局压力测试、模型调用或后续 Codex 监控自动化。
