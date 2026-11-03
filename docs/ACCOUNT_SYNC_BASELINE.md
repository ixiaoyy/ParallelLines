# 主站账号同步：现网源码基线同步

## 证据与范围

本次同步的是已在现网执行的主站资料输出及邮箱证明逻辑，不是重新设计账号同步。
本次从运行容器采集的实际 app 源码快照对应镜像：

`sha256:461f16fba78b21a332c397d26fd5fca206eb79bbeed68a4af08c81684e3d220c`

已将全部 162 个源码文件的原始摘要与 Git 基线逐项比较：

- 相对 `9c4318d2b9cafc4574e8d1b8558ffb6214f4e94e`，只有下列四文件不同，无额外或缺失源码。
- 相对性能提交 `2d7e9ca7ac0e600a05d6e381ab12dd92def74f01`，另有 `services/catalog.py`、`services/seo.py` 两个已批准性能差异；保留这两项，不从现网回退。
- 四份实际源码与固定候选 `main-profile-overlay/output-sha256.json` 一致，原字节同步。
- `models/user.py` 仅作断言，摘要为 `28f12234012452d38b13c05fb23facda3fe78ce0fc85438babd4ba63dfcbaff7`，没有替换模型、增加表/列或数据迁移。

| 文件（相对 `apps/api/app`） | 实际输出 SHA256 |
| --- | --- |
| `core/chat_sso.py` | `e589955c515d8a500c92a5b79639601cfa065f5ad83474f625bc549a3dad9a42` |
| `services/chat_sso.py` | `256b6304f223ca6227f85b607d5762071f03b34fabdd8953eb29ef0830b82e59` |
| `schemas/chat_sso.py` | `d60e5a5f8c6b69e92204597707978decd97ee8705b50400550549689ea690813` |
| `services/auth.py` | `f29b176e1c234152eec02b4d8b6787d39ed574bdae0dbab01c7f4c9aa595178a` |

完整摘要证据见 [现网源码清单](baselines/main-api-461f16-source-manifest.json)。其中不含源码正文、环境变量、凭证或用户数据。

## 已保留的行为

- 主站稳定 `sub`、会话、binding、有效期、一次性审批码及桥接认证边界不变。
- exchange/session-state 从当前主站记录读取 `name`、`username`、已验证邮箱及数据库 `role`。
  不用姓名/邮箱作为身份合并键，不从请求字段推断权限；非法角色明确拒绝，不补管理员或默认角色。
- 初始邮箱验证须有本用户、当前邮箱、有效消费时间的验证记录。
  邮箱变更须有成功兑换 token 的 JSON 布尔 `email_verified: true`；仅被作废或历史无标记的 token 不算证明。
- `confirm_email_change` 仅在成功路径、原有事务中给兑换 token 加证明；其他同时作废的 token 不加证明。
- 不改变主站角色/余额写入、下游角色映射、Chat 群组、依赖、环境或 worker。下游配置及共享 Nginx 由相应发布负责方核对。

## 合同与验证

响应字段扩展已在现网存在，所以同步必要的 OpenAPI 快照和生成类型：

- `apps/api/openapi/openapi.json` 仅 `ChatSsoExchangeResponse`、`ChatSsoStateResponse` 两组件变化。
- `apps/web/src/shared/api/generated.ts` 仅类型声明变化，无运行时代码；无对应响应类型的直接前端调用。
  其他 Web 源码未改，不重编译已验证的性能 dist。

新增 `apps/api/tests/test_chat_profile_baseline.py` 使用真实 Core、SQL adapter、ORM 模型、响应模型及
`AuthService.confirm_email_change`，只在独立内存 SQLite 中执行。18 项离线用例覆盖：

- 邮箱证明的当前邮箱匹配、消费不晚于有效期、旧 token 和非布尔标记；
- 主体稳定、资料与角色刷新、一次性码、防止失效会话继续返回资料；
- 请求字段不可注入角色、旧调用默认值不增权、原桥接凭证门禁；
- 真实邮箱变更消费与其他 token 作废、失败后的原会话回滚边界。

四源码与新用例的定向 Ruff、语法检查通过。没有连接生产数据库、发送邮件、发起模型请求或执行远程命令。
这些离线结果不代替真实 OIDC/Chat/New API 已认证链路、邮件投递及生产数据库验收。
发布与运行配置切换仍须使用已批准窗口；不把源码匹配记录当成完成部署。
