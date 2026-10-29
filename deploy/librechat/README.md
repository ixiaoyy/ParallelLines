# 家庭 GPT：服务器接入与回滚

本目录是独立的 LibreChat 部署配置。只连接 OpenAI，保留原版聊天界面；第一版仅文字、JPEG/PNG/WebP 图片及图文混合。没有 New API、自建聊天后台、PDF/RAG 或其他供应商。

**当前使用唯一的平行线主站登录/注册入口。不要运行 `create-user` 再建一套聊天账号。** 主站有效账号通过 OIDC 建立聊天身份，模型调用资格另行控制。本轮未授权具体账号及额度，默认继续拒绝 GPT 请求。现成 Admin Panel 对这些 OIDC 身份的安全适配尚未开放，`/api/admin` 已隔离；当前不能从该后台直接给 `pl-*` 账号授权。当前认证与运维以 [SSO.md](./SSO.md) 为准。

`OPENAI_API_KEY` 与 `OPENAI_CHAT_MODELS` 的模板均为空。原有模拟验收保持独立，生产 Compose 不包含模拟模型，缺 Key 时不会自动切换到 mock。生产发布状态以 GitHub Actions 的 `Deploy family chat` 和线上检查为准。

## 交接文件与固定版本

- 本目录位于项目的 `deploy/librechat/`，通过独立发布流程启动聊天服务。
- `/chat` 代理位于 `deploy/nginx/default.conf`；先启动聊天服务并确认健康，再激活该路由，不重新构建游戏 Web/API。
- 使用独立 Compose 项目 `parallellines-chat`，通过已有平行线 Docker 网络提供 `librechat:3080`。不修改根 `docker-compose.yml`，不重建游戏 Web/API。
- 主程序：`v0.8.9-rc1`，镜像 digest `sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5`。
- 后台：commit `f2601cbf3216a62c12e5f9d21810eb9ada95fa63`，digest `sha256:90b21c56f9494577304f9cf3dde9f770e3dba35b0ce319fbb868aa1a6745248a`。
- MongoDB、附件、日志、应用数据采用该项目的独立命名卷，不使用平行线 MySQL 或本地模拟数据库。

主程序仍是预发布版、后台仍是 Preview，不能把配置准备当作已验证的生产稳定性。

## 1. 首次初始化说明与当前 SSO 运维

下列应用密钥初始化仅供全新安装参考；当前服务器已经初始化，不要重复执行或重建认证材料。首次初始化会新建五项持久应用安全密钥，须获得所有者明确同意后执行。它不创建管理员账号、OpenAI API Key 或 SSH 访问凭据。已有 `.env` 保留，不读取或覆盖。

当前统一登录使用 Actions 的 `Deploy family chat / mode=sso`。`mode=preflight` 只读检查资源与服务状态；旧 `mode=deploy` 的首次安装路径不包含 SSO，不能用于维护当前实例。初始化新安全材料仍需所有者明确同意；已有材料不得覆盖。

当前 SSO 发布叠加 `compose.disabled.yaml`，把容器的 OpenAI Key 设为空，即使服务器 `.env` 已填写也保持停用；候选模型列表单独保留。账号资格和额度尚未确定，本说明的维护命令继续保留停用层与 SSO 层，不构成模型开通操作。主站与聊天发布共用串行队列。

```sh
cd /opt/parallellines/deploy/librechat
sudo docker pull registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5
sudo docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/integration" --entrypoint node \
  registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5 \
  /integration/init.cjs
chmod 600 .env
```

`init.cjs` 从模板创建 `.env`，仅生成本地登录/会话/加密所需随机值；OpenAI Key 和模型选择继续为空。已有 `.env` 会保留，脚本不读取或覆盖它。长期保存这些应用密钥，回滚和容器重建均不重新生成。

初始化的确切范围：

| 变量 | 用途 | 随机字节数 |
|---|---|---|
| `JWT_SECRET` | 登录令牌签名 | 32 |
| `JWT_REFRESH_SECRET` | 刷新令牌签名 | 32 |
| `CREDS_KEY` | LibreChat 凭据加密密钥 | 32 |
| `CREDS_IV` | LibreChat 加密初始化参数 | 16 |
| `ADMIN_PANEL_SESSION_SECRET` | 管理后台会话签名 | 32 |

所有值使用服务器 Node `crypto.randomBytes` 生成并编码为十六进制，仅保存到本目录 `.env`，权限 `0600`，不进入 Git、日志或聊天。修改签名密钥会使已有会话失效，修改加密参数可能使已保存的加密数据无法解密；因此需持续备份保存。初始化不创建任何管理员/家人账号，不授予模型使用权限，不创建远程访问凭据。

2026-10-29 的服务器只读预检显示可用内存约 3783 MiB、根盘剩余 18 GiB，网络为 `parallellines_default`。本地同版本已有图文验收后的占用约为 API 379 MiB、MongoDB 187 MiB、后台 84 MiB。新增容器分别设置 1 GiB、768 MiB、384 MiB 上限，MongoDB 缓存为 0.25 GiB；上线后仍需核对实际健康和资源占用。

当前已有平行线网络通常是 `parallellines_default`。以下为 SSO 服务检查；`REVISION` 必须替换成当前已部署的完整提交 SHA，并在同一终端保持 `CHAT_SSO_RELEASE`。不要只加载基础 Compose 文件：

```sh
cd /opt/parallellines/deploy/librechat
export CHAT_SSO_RELEASE=REVISION
sudo docker network ls --format '{{.Name}}'
sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml config --quiet
sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml up -d
```

如有多个网络，在原项目目录只读确认 nginx 的实际网络，再选平行线自己的 default 网络：

```sh
cd /opt/parallellines
docker inspect "$(docker compose ps -q nginx)" --format '{{range $name,$value := .NetworkSettings.Networks}}{{println $name}}{{end}}'
```

主 nginx 已有 Docker DNS resolver；新增代理用变量延迟解析 LibreChat 服务。聊天服务暂未启动时，不会阻止游戏站 nginx 启动。路由通过正常 Nginx 发布流程生效；手动更新时只重建边缘 Nginx，不重启游戏 Web/API。配置文件是文件 bind mount，Git 替换文件后仅 reload 可能仍读到旧 inode。

```sh
cd /opt/parallellines
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml up -d --wait --wait-timeout 90 --no-deps --build --force-recreate nginx
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml exec -T nginx nginx -t
```

浏览器标签及欢迎标题为“平行线 · AI 聊天”。原生模型下拉展示候选型号，停用原因在页脚和菜单描述中以小号文字展示；基础 OpenAI 授权目录仍为空，没有个人 Key 输入分支。菜单展示不授予模型权限，未配置服务或未获账号授权时请求被拒绝，不产生模拟回复。统一登录及后台入口的当前约束见 [SSO.md](./SSO.md)。

## 2. Key 填在哪里，模型怎样选

真实启用前，先确认账户促销额度的适用范围，以及服务器和实际使用者所在地都符合当前官方服务地区要求。境外服务器本身不代表可以绕过实际使用者的地区限制；该资格核验尚未完成时，保持模型调用关闭；已填写的服务器 Key 保留，不读取或覆盖。

**只在服务器编辑 `/opt/parallellines/deploy/librechat/.env`：**

```sh
nano /opt/parallellines/deploy/librechat/.env
```

- `OPENAI_API_KEY=`：用户亲自填写自己的 OpenAI API Key。
- `OPENAI_CHAT_MODELS=`：填写获准使用、支持文字和图片的模型 ID，多个 ID 用逗号分隔。

模型不是 ChatGPT 界面显示名。不要把 Key 填到前端、源码、YAML、聊天消息、Git 或命令行参数。家庭用户只登录账号，模型 Key 由服务器统一持有。后台容器也不接收 OpenAI Key。

2026-10-29 按用户最新选择配置的服务器候选列表为 `gpt-6-luna,gpt-6.1-terra,gpt-6.1-sol`，默认 GPT-6 Luna（官方 Luna 当前是 6 系列，界面不会写成 6.1 Luna），从 [OpenAI 模型目录](https://developers.openai.com/api/docs/models) 及对应模型页重新核验：

| 可选模型 | 用途提示 | 官方文档 |
|---|---|---|
| `gpt-6-luna` | 成本敏感的日常聊天；固定 LibreChat 源码已有该系列识别 | [模型说明](https://developers.openai.com/api/docs/models/gpt-6-luna) |
| `gpt-6.1-terra` | 文字与图片任务的质量选项 | [模型说明](https://developers.openai.com/api/docs/models/gpt-6.1-terra) |
| `gpt-6.1-sol` | 更复杂的文字与图片任务 | [模型说明](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |

这三个正式型号均支持文字/图片输入、文字输出及 Responses；已核对固定 LibreChat 版本的 Responses 路径。未进行真实收费请求，文档与源码核验不代表当前账户已获访问权限。初始化模板仍留空；候选更新脚本 `configure-models.cjs` 只替换 `.env` 的 `OPENAI_CHAT_MODELS` 行，其他字节和文件权限保留，不创建或修改任何用户/管理员/profile。维护现有实例须保留 SSO overlay；旧 `mode=models` 若不支持当前 Compose 组合会拒绝执行，不能绕过它的模式检查。候选以无密钥的 `/app/data/family-config/selected-models.json` 留档；缺 Key 时实际可调用目录及授权导入模板继续为空。原生模型下拉会展示候选及受限原因，菜单可见不代表已经获准调用。只有有效 Key 和指定目标账号 USER profile 的模型权限均满足后才能发起请求。查看 [当前价格](https://developers.openai.com/api/docs/pricing)；不为 Sol 配置 `reasoning.effort=none`，该型号不支持此值。旧 mock 的 `gpt-4o-mini` 不会成为生产默认。

模型列表已固定上述三项并默认 Luna；修改后需要**重建容器以重读 env**。下面的维护命令保留当前停用状态，并不会开通真实调用；先按第 1 节设置当前 `CHAT_SSO_RELEASE`：

```sh
cd /opt/parallellines/deploy/librechat
sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml up -d --force-recreate librechat
```

`restart` 不会重新载入 Compose 的 env 文件。模型目录与 preset 在每次启动时生成，不把密钥序列化进生成的 YAML。采用原生 OpenAI 及 `useResponsesApi: true`；[官方图片输入说明](https://developers.openai.com/api/docs/guides/images-vision) 区分了 Responses 的 `input_text`/`input_image` 与旧 Chat Completions 的结构。

模型 ID 的选择通过服务器环境完成。`approved-user-profile.yaml` 是无密钥的候选模板，生成文件不会自动修改任何用户权限。当前 Admin Panel 尚不能管理主站 OIDC 身份；不要把模板导入 Base、整个 USER 角色或全体用户组来绕过这一限制。

**填 Key 和选择模型不等于给全家授权。** 基础配置始终使用空模型授权目录，模型规格只提供菜单候选，新账号默认不能调用 GPT。初始化和容器重建不会自动修改任何用户授权。

具体账号的模型与额度配置需在用户确认目标账号、额度及适用条件后另行完成；本轮不创建管理员、不映射主站管理员权限、不修改账号记录。现成 Admin Panel 的 OIDC 身份适配未开放，不能将后台配置能力的本地研究结论当作生产可操作入口。

## 3. 无费用检查与真实效果验证

先进入 `/opt/parallellines/deploy/librechat`，按第 1 节设置当前 `CHAT_SSO_RELEASE`，再做不调用模型的检查：

```sh
sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml ps
sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml exec -T librechat node -e \
"const fs=require('fs');const c=JSON.parse(fs.readFileSync('/app/data/family-config/librechat.yaml','utf8'));const p=JSON.parse(fs.readFileSync('/app/data/family-config/approved-user-profile.yaml','utf8'));console.log(JSON.stringify({serverGptConfigured:p.modelSpecs.list.length>0,defaultAccountAccess:false,configuredModels:p.endpoints.openAI.models,baseModels:c.endpoints.openAI.models,welcome:c.interface.customWelcome}));"
curl -fsS https://pingxingxian.space/chat/readyz
```

这些检查使用第 1 节的当前 `CHAT_SSO_RELEASE`，只显示启用状态和模型 ID，不打印 Key，不调用收费模型。`config --quiet` 只验证 Compose；不要用普通 `docker compose config` 的完整输出作截图或发送到聊天，因为它会展开环境值。

后续由用户确认适用条件、完成指定账号授权并明确允许费用后，再在该账号聊天页手动发送一次文字和一张不含个人信息的普通图片，检查回答是否对应图片、历史是否保存、余额是否扣减，并与供应商 usage 对照。这一步**可能收费**，目前未执行。现有模拟验收证明接入流程，不能证明真实 GPT 图像识别、Responses 兼容性或真实账单。

## 4. 主站账号、后台及额度现状

所有聊天用户使用平行线主站账号。聊天侧的密码登录、独立公开注册及原生管理员 OAuth 兑换均已关闭；不新建独立家人或管理员账号，不按邮箱自动合并账号。

管理后台容器仍只绑定服务器 `127.0.0.1:3091`，但 OIDC 管理员身份与会话适配尚未开放，`/api/admin` 保持隔离。因此本轮没有可供用户直接操作的按人授权/额度后台入口，也没有通过 CLI 修改任何真实账号余额。不要通过创建旧式密码管理员、全局放开模型或解除该隔离来代替适配。

后续最小待办为确认目标主站账号与额度，然后完成管理身份适配或另行授权的最小按人配置流程。当前保持基础模型权限为空。现有 `balance` 配置和生成的 profile 模板只是能力准备，不代表任何账号已开通。

默认 10000 credits 只是初始模板值，尚不是用户确认的额度。`startBalance` 只初始化新余额，不给已有账号加额。额度预留不能保证末次已接纳输出绝不超额。固定版本对新模型、缓存和长上下文的价格识别可能滞后，**credits 不应当作精确当前美元账单或供应商硬预算**。当前 preset 使用 128K 应用上下文和 4096 输出上限，真实费用仍需后续获准调用核验。

## 5. 最小回滚

仅保持模型停用、保留账号和历史：保留 `compose.disabled.yaml` 并执行上面的含双 env、SSO overlay 的重建命令。不要为停用覆盖用户已填写的 Key。界面保持未启用状态，不会转成 mock。

需要撤回整个聊天入口时，从本次路由提交提取仅含 Nginx 的补丁，检查后反向应用，保留其他提交和部署目录：

```sh
cd /opt/parallellines
git show 758dbc621a20857a30476d940a776aa51267c5c2 -- deploy/nginx/default.conf > /tmp/family-chat-route.patch
git apply -R --check /tmp/family-chat-route.patch
git apply -R /tmp/family-chat-route.patch
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml up -d --wait --wait-timeout 90 --no-deps --build --force-recreate nginx
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml exec -T nginx nginx -t
```

若检查冲突，停止反向应用并核对后续 Nginx 改动，不用整文件回退覆盖。路由回滚需要纳入后续仓库发布，避免下次发布重新带回入口。然后只停止聊天栈：

```sh
cd /opt/parallellines/deploy/librechat
sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml stop
```

保留 `.env` 和所有命名卷。不要 `down -v`、清空 MongoDB、轮换 JWT/加密值或用整文件 checkout 覆盖同期游戏发布。当前回滚说明针对这次首次接入；未来升级数据库/镜像时，先备份数据并核验迁移兼容性。

## 子目录图片补丁

`patches/validateImageRequest.js` 只把固定版图片权限适配器的路径基准改为代理移除 `/chat` 后的内部 `/images/`，不关闭鉴权、不开放目录、不绕过 owner/ACL。此前本人、他人、匿名及编码路径检查已通过。镜像升级时重新核验该适配器，不扩展为长期 fork。
