# 海外动态发布：20261117-overseas

本版本只替换 `parallellines-community-content`，以发布前现用独立 worker 的镜像为基底，离线覆盖 `community_schedule.py`、`scheduled_content.py`、`overseas_content.py`。不提交推送 Git，不重启主站/API/数据库/网关/Chat，不改数据库结构或历史业务数据，不重铺 h1 基底，不执行迁移，不修改真实环境文件或原激活水位。正常调度/发布仍按原有事务写队列、日志及新帖子。包内 `context/` 只含这三个已核文件，`before/`、`production-before.json` 是本次非敏感前像。

服务器目录：`/opt/parallellines/.deployment/community-content/20261117-overseas/`。获准准备本版本包时取 [共享 rollout.py](../rollout.py) 并以原文件名复制到该目录；使用该目录固定的覆盖和恢复配方，不使用跨版本软链接。本入口不会覆盖旧 `20261115-h1` 或 `20261116-copy-no-living` 目录、镜像标签和管理记录。

## 独立检查与切换

```sh
python3 /opt/parallellines/.deployment/community-content/20261117-overseas/rollout.py status
python3 /opt/parallellines/.deployment/community-content/20261117-overseas/rollout.py apply
python3 /opt/parallellines/.deployment/community-content/20261117-overseas/rollout.py status
```

仅当次上线授权内执行 `apply`。先准备停止态新版与恢复实例，再核配置完全保留、其他容器不变且内容队列空闲，才停止旧实例并保留。旧实例重命名为 `parallellines-community-content-before-20261117-overseas`，不删除。任何时刻只运行一个内容 worker；不并行运行 `--once`。旧 h1 管理入口不再用于检查新版，使用本版本独立 `status`。

`status` 只检查本次精确容器和镜像、Docker 健康、新实例启动后的有效心跳及其他容器状态；不入队或发帖。健康不代表海外来源连通或发布成功，须另以只读预览检查当前来源和现有账号/版块，并在下一自然时段核队列、唯一帖子及公开页面，不提前补发错过的时段。

## 独立恢复

```sh
python3 /opt/parallellines/.deployment/community-content/20261117-overseas/rollout.py recover
python3 /opt/parallellines/.deployment/community-content/20261117-overseas/rollout.py status
```

恢复入口在切换前已上传，并提前构建恢复镜像和停止态恢复容器。旧原始容器、旧镜像与原有持久快照始终保留。恢复先精确停止并保留失败新版，再启动基于旧镜像的兼容恢复实例；它保留原五项功能、继续停用生活小问，只把可能遗留的 `overseas` 任务记为 `skipped/overseas_release_reverted`。不清队列、不删帖子、不回滚历史业务数据，也不恢复旧自动任务；正常消费仍记录任务、日志及跳过回执。不得直接启动原始旧容器消费它不认识的海外任务。

命令超时或回执丢失，先运行独立 `status` 并核 `rollout.json`，不要重复 `apply`、删除状态、强制覆盖名称或启动第二实例。`apply` 不是可重跑的安装入口；已记录的失败通过本版本恢复入口处理。遇身份或配置漂移停止操作，不动其他服务。
