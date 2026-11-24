# 海外动态渲染修订：20261117-overseas-render

首轮自然调度已于 2026-11-17 18:00 发布 topic802：五条原帖、五条来源防重审计及唯一时段回执。公开接口发现长德文标签超过圈子小型渲染器的160字符上限，导致一条原帖显示成Markdown；反斜杠转义也未被该渲染器处理。

本修订以当前海外 worker 镜像 `cccb5fadb4f5` 为基底，离线只覆盖 `app/services/scheduled_content.py`。海外输出改用已有 `frontier_news._markdown_label` 的150字符标签，不加无效反斜杠，自动说明使用普通段落。旧栏目、链接身份、防重键、账号、原帖时间、原激活水位及六项调度不变。不改论坛渲染器，不重启 API 或其他服务，不新增付费调用。

本版本目录：`/opt/parallellines/.deployment/community-content/20261117-overseas-render/`。获准准备本版本包时取 [共享 rollout.py](../rollout.py) 并以原文件名复制到该目录；使用该目录固定的单文件覆盖和恢复配方，不使用跨版本软链接。旧版本目录、容器和镜像保留，不覆盖首版。

## 实际结果

- 已切换至容器 `bf540a9de230`、镜像 `18583c4e39dd`；Docker healthy、新启动后心跳有效、运行源码与本包一致，原配置和其他容器 ID/启动时间保持。
- 本次渲染修复四项定向回归通过（真实论坛 renderer、短摘、两种跨平台去重）；单文件版本发布协议九项 mock 检查及 Ruff 通过。没有通过真实故障/回退演练验证恢复入口。
- 用户明确确认单帖修正后，以原作者编辑 topic802 首帖1216；revision58保存原稿。原五条来源、标题、作者、时间、顺序及11条原发布审计保持，没有重新发帖。
- 匿名公开页面和帖子接口均 `200`，公开渲染有五个正确 href、无多余反斜杠，和原五条链接逐条同序相符；原页面浏览器视觉检查受连接超时限制。

```sh
python3 /opt/parallellines/.deployment/community-content/20261117-overseas-render/rollout.py apply
python3 /opt/parallellines/.deployment/community-content/20261117-overseas-render/rollout.py status
```

同样先构建停止态正式/恢复实例，重验当前配置、源码、队列空闲和其他服务，再串行停止旧 worker、保留并切换新版。不得并行启动 `--once` 或第二 worker；回执丢失先查 `status`，不重跑 `apply`。

## 修正首篇既有内容

只从 topic802 已发布的五条原文短摘生成格式修正，不重新采集选稿。通过现有作者的 `ForumService.update_post` 修正首帖，保留标题、作者、链接、时间、条目顺序和来源/时段审计；该入口会新增原稿 revision、编辑审计并更新搜索索引。调用前核正文及更新时间未变、账号真实权限/状态、链接筛选和内容策略；有审核/禁言风险则停止，不修改角色/信任或绕过审核。结果必须以公开渲染含五个可点击原帖链接、元信息无多余反斜杠及防重审计不变验收，不将尝试调用当成功。

## 独立恢复

```sh
python3 /opt/parallellines/.deployment/community-content/20261117-overseas-render/rollout.py recover
python3 /opt/parallellines/.deployment/community-content/20261117-overseas-render/rollout.py status
```

恢复实例基于上一版海外镜像，原 worker 源码不变，已能解析海外任务，保留全部六项调度、生活停用和原持久挂载。回退会回到首版格式缺陷，不清队列、不删除已发布帖子、不撤销原稿 revision，也不回滚业务数据。原五项和海外帖子正常消费仍会写队列/日志/新帖；不宣称恢复完全无数据库写入。
