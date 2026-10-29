# 家庭 GPT：服务器接入与回滚

本目录是独立的 LibreChat 部署配置。只连接 OpenAI，保留原版聊天和管理后台；第一版仅文字、JPEG/PNG/WebP 图片及图文混合。没有 New API、自建聊天后台、PDF/RAG 或其他供应商。

`OPENAI_API_KEY` 与 `OPENAI_CHAT_MODELS` 的模板均为空。原有模拟验收保持独立，生产 Compose 不包含模拟模型，缺 Key 时不会自动切换到 mock。生产发布状态以 GitHub Actions 的 `Deploy family chat` 和线上检查为准。

## 交接文件与固定版本

- 本目录位于项目的 `deploy/librechat/`，通过独立发布流程启动聊天服务。
- `/chat` 代理位于 `deploy/nginx/default.conf`；先启动聊天服务并确认健康，再激活该路由，不重新构建游戏 Web/API。
- 使用独立 Compose 项目 `parallellines-chat`，通过已有平行线 Docker 网络提供 `librechat:3080`。不修改根 `docker-compose.yml`，不重建游戏 Web/API。
- 主程序：`v0.8.9-rc1`，镜像 digest `sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5`。
- 后台：commit `f2601cbf3216a62c12e5f9d21810eb9ada95fa63`，digest `sha256:90b21c56f9494577304f9cf3dde9f770e3dba35b0ce319fbb868aa1a6745248a`。
- MongoDB、附件、日志、应用数据采用该项目的独立命名卷，不使用平行线 MySQL 或本地模拟数据库。

主程序仍是预发布版、后台仍是 Preview，不能把配置准备当作已验证的生产稳定性。

## 1. 在服务器初始化，不填写真实模型 Key 也可启动

以下初始化会新建五项持久应用安全密钥，须获得所有者明确同意后执行。它不创建管理员账号、OpenAI API Key 或 SSH 访问凭据。已有 `.env` 保留，不读取或覆盖。

也可使用仓库 Actions 的 `Deploy family chat`：`mode=preflight` 只检查真实资源、Docker 网络、服务状态及 `.env` 是否存在；`mode=deploy` 启动服务。只有在所有者明确同意生成上述五项密钥后，才勾选 `initialize_application_secrets`。这一步不会创建 LibreChat 管理员账号。

此 Actions 发布总会叠加 `compose.disabled.yaml`，把容器的 OpenAI Key/模型设为空，即使服务器 `.env` 已有填写也保持停用。下文用户手动启用使用基础 `compose.production.yaml`，不叠加停用覆盖文件。主站与聊天发布共用串行队列，后续发布不会取消正在执行的远端操作。

```sh
cd /opt/parallellines/deploy/librechat
docker pull registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5
docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD:/integration" --entrypoint node \
  registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5 \
  /integration/init.cjs
chmod 600 .env
```

`init.cjs` 从模板创建 `.env`，仅生成本地登录/会话/加密所需随机值；OpenAI Key 和模型选择继续为空。已有 `.env` 会保留，脚本不读取或覆盖它。长期保存这些应用密钥，回滚和容器重建均不重新生成。

检查已有平行线 nginx 所在网络，按实际结果在 `.env` 设置 `PARALLELLINES_NETWORK`（通常是 `parallellines_default`）：

```sh
docker network ls --format '{{.Name}}'
docker compose --env-file .env -f compose.production.yaml config --quiet
docker compose --env-file .env -f compose.production.yaml up -d
```

如有多个网络，在原项目目录只读确认 nginx 的实际网络，再选平行线自己的 default 网络：

```sh
cd /opt/parallellines
docker inspect "$(docker compose ps -q nginx)" --format '{{range $name,$value := .NetworkSettings.Networks}}{{println $name}}{{end}}'
```

主 nginx 已有 Docker DNS resolver；新增代理用变量延迟解析 LibreChat 服务。聊天服务暂未启动时，不会阻止游戏站 nginx 启动。应用 `/chat` 补丁后执行原项目的 `nginx -t`，成功后 reload；不要因聊天配置重启游戏业务服务。

```sh
cd /opt/parallellines
docker compose exec -T nginx nginx -t
docker compose exec -T nginx nginx -s reload
```

此时网页显示“GPT 尚未启用，请联系管理员在服务器完成密钥和模型配置。”，原生 OpenAI 模型目录为空、没有个人 Key 输入分支。强行调用模型也会被原版模型目录/密钥校验拒绝，不产生模拟回复。

## 2. Key 填在哪里，模型怎样选

真实启用前，先确认账户促销额度的适用范围，以及服务器和实际使用者所在地都符合当前官方服务地区要求。境外服务器本身不代表可以绕过实际使用者的地区限制；该资格核验尚未完成时，只保留无 Key/模拟验证。

**只在服务器编辑 `/opt/parallellines/deploy/librechat/.env`：**

```sh
nano /opt/parallellines/deploy/librechat/.env
```

- `OPENAI_API_KEY=`：用户亲自填写自己的 OpenAI API Key。
- `OPENAI_CHAT_MODELS=`：填写获准使用、支持文字和图片的模型 ID，多个 ID 用逗号分隔。

模型不是 ChatGPT 界面显示名。不要把 Key 填到前端、源码、YAML、聊天消息、Git 或命令行参数。家庭用户只登录账号，模型 Key 由服务器统一持有。后台容器也不接收 OpenAI Key。

截至 2026-10-29 从 [OpenAI 模型目录](https://developers.openai.com/api/docs/models) 核验的可选 ID 包括：

| 可选模型 | 用途提示 | 官方文档 |
|---|---|---|
| `gpt-6-luna` | 成本敏感的日常聊天；固定 LibreChat 源码已有该系列识别 | [模型说明](https://developers.openai.com/api/docs/models/gpt-6-luna) |
| `gpt-6.1-sol` | 更复杂的文字与图片任务 | [模型说明](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |
| `gpt-6-astra` | 更高能力、相应更高成本 | [模型说明](https://developers.openai.com/api/docs/models/gpt-6-astra) |

这些是当前文档中的选项，不是替用户选定的生产默认。模板故意留空。模型存在于文档不代表当前账户已获得访问权限；填写前查看账户可用模型与 [当前价格](https://developers.openai.com/api/docs/pricing)。`gpt-6.1-terra` 虽在官方目录中，但此固定 LibreChat 版本缺少该系列的专门适配，暂不作为已验证候选。旧 mock 的 `gpt-4o-mini` 不会成为生产默认。

例如，用户决定选择日常模型后可填写 `OPENAI_CHAT_MODELS=gpt-6-luna`。修改后需要**重建容器以重读 env**：

```sh
cd /opt/parallellines/deploy/librechat
docker compose --env-file .env -f compose.production.yaml up -d --force-recreate librechat
```

`restart` 不会重新载入 Compose 的 env 文件。模型目录与 preset 在每次启动时生成，不把密钥序列化进生成的 YAML。采用原生 OpenAI 及 `useResponsesApi: true`；[官方图片输入说明](https://developers.openai.com/api/docs/guides/images-vision) 区分了 Responses 的 `input_text`/`input_image` 与旧 Chat Completions 的结构。

模型 ID 的初始选择通过服务器环境完成；原版后台仍可维护模型规格和按人配置。若后台已有模型/用户覆盖，切换模型时一并检查这些覆盖，确保家人看到预期模型。

**填 Key 和选择模型不等于给全家授权。** 基础配置始终使用空模型目录与空的强制模型规格，新账号默认不能调用 GPT。初始化和容器重建不会自动修改任何用户授权。

对确认符合当前 OpenAI 适用地区等条件的用户，管理员在原版后台选择该用户的 USER profile，再导入启动时生成的无密钥覆盖配置：

```sh
docker compose --env-file .env -f compose.production.yaml exec -T librechat \
  cat /app/data/family-config/approved-user-profile.yaml > /tmp/approved-user-profile.yaml
```

该文件只含已选择的模型、Responses preset 和界面选项，没有 Key。通过自己的安全管理通道取得此文件，在 Configuration → **目标用户 profile** → Import YAML 导入，核对导入预览的目标明确是 **User: 该用户**、审查清单只影响该用户后保存；向导中的目标保持当前用户，不改成 Base、整个 USER 角色或面向全体的组。也可在同一用户 profile 的 AI providers 与 Model specs 页面逐项配置相同内容。没有经过确认的账号继续保持空目录，不自动接其他厂商。按账号授权不识别实时所在地，获授权用户仍需在实际使用时符合当前地区等条件。

撤销某个用户的 GPT 使用时，在其 USER profile 使用字段的恢复继承/移除覆盖操作，移除 OpenAI Models 覆盖并移除该用户新增的模型规格，继承 Base 空目录；复核该用户的有效模型目录为空，同时检查是否另有组/角色授权。也可明确停用整个 USER profile，但这会同时停用该 profile 中的额度等其他覆盖。**不要把导入空数组 YAML 当作撤权**：此版本导入器可能跳过空列表，模型规格列表也按名称合并。此处利用现有按用户配置，不新增定位、IP绕行或复杂地域系统，也不假定任何人的当前所在地。

## 3. 无费用检查与真实效果验证

先做不调用模型的检查：

```sh
docker compose --env-file .env -f compose.production.yaml ps
docker compose --env-file .env -f compose.production.yaml exec -T librechat node -e \
"const fs=require('fs');const c=JSON.parse(fs.readFileSync('/app/data/family-config/librechat.yaml','utf8'));const p=JSON.parse(fs.readFileSync('/app/data/family-config/approved-user-profile.yaml','utf8'));console.log(JSON.stringify({serverGptConfigured:p.modelSpecs.list.length>0,defaultAccountAccess:false,configuredModels:p.endpoints.openAI.models,baseModels:c.endpoints.openAI.models,welcome:c.interface.customWelcome}));"
curl -fsS https://pingxingxian.space/chat/readyz
```

这些只显示启用状态和模型 ID，不打印 Key，不调用收费模型。`config --quiet` 只验证 Compose；不要用普通 `docker compose config` 的完整输出作截图或发送到聊天，因为它会展开环境值。

后续由用户确认适用条件、完成指定账号授权并明确允许费用后，再在该账号聊天页手动发送一次文字和一张不含个人信息的普通图片，检查回答是否对应图片、历史是否保存、余额是否扣减，并与供应商 usage 对照。这一步**可能收费**，目前未执行。现有模拟验收证明接入流程，不能证明真实 GPT 图像识别、Responses 兼容性或真实账单。

## 4. 家人账号、后台及额度

公开注册与社交注册关闭。在新数据库中先由服务器所有者交互创建管理员，再创建家人：

```sh
docker compose --env-file .env -f compose.production.yaml exec -w /app librechat npm run create-user
```

密码在终端交互输入；不作为命令行参数。当前平行线 JWT 和 FableSpace 票据不能直接复用为通用 OIDC，所以本版使用 LibreChat 独立家庭账号。

后台仅绑定服务器 `127.0.0.1:3091`。在自己的电脑建立授权 SSH 隧道后访问，不另开放公网后台：

```sh
ssh -L 3091:127.0.0.1:3091 <你的服务器登录目标>
```

在浏览器打开 `http://127.0.0.1:3091`，用 LibreChat 管理员登录。路径：Configuration → 家人 user profile → System → Balance & credits，设置每人数量和周期。`refillMode` 在这个后台版本只读，由 `base-config.json` 中的 `reset` 控制；手动增减当前余额使用官方交互命令：

```sh
docker compose --env-file .env -f compose.production.yaml exec -w /app librechat npm run add-balance
docker compose --env-file .env -f compose.production.yaml exec -w /app librechat npm run set-balance
```

默认 10000 credits 只是初始配置，管理员按家庭用量调整。`startBalance` 只初始化新余额，不给已有账号加额。额度预留不能保证末次已接纳输出绝不超额。固定版本对新模型、缓存和长上下文的价格识别可能滞后，例如 6.1 Sol 会匹配旧 Sol 缓存费率；**credits 不应当作精确当前美元账单或供应商硬预算**。当前 preset 使用 128K 应用上下文和 4096 输出上限，真实费用仍需后续获准调用核验。

## 5. 最小回滚

仅停用模型、保留账号和历史：在服务器 `.env` 把 `OPENAI_API_KEY` 与 `OPENAI_CHAT_MODELS` 留空，然后执行上面的 `up -d --force-recreate librechat`。界面恢复未启用状态，不会转成 mock。

需要撤回整个聊天入口时：先在项目根目录对 `main-chat-proxy.patch` 执行 `git apply -R --check`，确认仅涉及该代理后反向应用；执行原 nginx 的 `nginx -t` 并 reload。保留部署目录，不反向删除整个集成包。然后只停止聊天栈：

```sh
cd /opt/parallellines/deploy/librechat
docker compose --env-file .env -f compose.production.yaml stop
```

保留 `.env` 和所有命名卷。不要 `down -v`、清空 MongoDB、轮换 JWT/加密值或用整文件 checkout 覆盖同期游戏发布。当前回滚说明针对这次首次接入；未来升级数据库/镜像时，先备份数据并核验迁移兼容性。

## 子目录图片补丁

`patches/validateImageRequest.js` 只把固定版图片权限适配器的路径基准改为代理移除 `/chat` 后的内部 `/images/`，不关闭鉴权、不开放目录、不绕过 owner/ACL。此前本人、他人、匿名及编码路径检查已通过。镜像升级时重新核验该适配器，不扩展为长期 fork。
