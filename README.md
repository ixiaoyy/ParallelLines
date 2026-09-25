# 平行线 · AI 游戏收录

平行线收录可直接游玩的 AI 游戏与独立项目。访客可以按分类浏览、按项目名称搜索、查看作者和评分，再打开游戏原站。站内作品也保留直达入口。

## 网站功能

- 游戏目录：分类、名称搜索、最新与热门排序；游戏卡片展示封面、作者及评分。
- 游客评分：每个 IP 对同一项目只能提交一次 1–5 心评分。
- 游戏投稿：游客填写分类、项目名和 HTTPS 链接，可选填作者、联系方式及封面；管理员审核通过后才公开。
- 目录后台：`/admin` 登录后可查看流量统计、审核投稿、维护分类与项目。

公开站不要求登录。目录、评分和投稿由 API 提供；项目资料存于 MySQL，图片可使用本地存储或 S3 兼容对象存储。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `apps/web` | Vue 3、Vite、TypeScript 前端 |
| `apps/api` | FastAPI、SQLAlchemy、Alembic 后端 |
| `apps/api/alembic` | 数据表与初始目录迁移 |
| `static/web/catalog` | 目录封面等静态图片源文件 |
| `deploy/nginx` | 公网站点与 API 的 Nginx 配置 |

## 本地启动

仓库使用 pnpm 11 和 Python 项目的 uv。先复制 `apps/api/.env.example` 为 `apps/api/.env`，设置本地 `DATABASE_URL`、`JWT_SECRET_KEY` 等配置。

使用 Docker Compose：

```powershell
docker compose up -d --build
```

Compose 会启动 MySQL、Redis、API、静态 Web、Nginx 和后台清理 worker，并在 API 启动时执行 Alembic 迁移。网站地址为 `http://localhost`，API 健康检查为 `http://localhost/healthz`。Compose 使用的数据库地址应指向服务名 `db`。

分别运行前后端：

```powershell
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

```powershell
pnpm install
pnpm dev:web
```

前端通过 `VITE_API_BASE_URL` 连接 API；本地默认是 `http://127.0.0.1:8000/api/v1`，Compose 构建使用同源的 `/api/v1`。

## 内容与图片

管理员在 `/admin` 维护目录。隐藏项目不会出现在公开目录；游客投稿在审核通过前也不会公开。初始游戏及分类由 Alembic 数据迁移导入，之后可在后台调整。

部分游戏的收录线索来自 [awesome-gpt-6-astra](https://github.com/MartinDelophy/awesome-gpt-6-astra)。感谢维护者 martindelophy；各游戏的作者仍按项目本身署名。

内置目录封面位于 `static/web/catalog`，正式页面从 `img.pingxingxian.space` 的版本化目录读取。新图片应压缩后上传到新版本路径，避免覆盖旧图；管理员和游客提交的封面由上传服务管理，待审封面只在后台预览。

本地上传默认保存在 `apps/api/var/uploads`；Compose 将上传文件映射到宿主机的 `/opt/parallellines/var/uploads`。如使用 S3 兼容存储，在 `apps/api/.env` 配置 `UPLOAD_STORAGE_BACKEND=s3` 及对应连接参数，不要把密钥提交到仓库。

## 检查与部署

```powershell
pnpm typecheck:web
pnpm lint:web
pnpm build:web
pnpm lint:api
```

`pnpm test:api` 需要事先配置可用的测试数据库，不能直接使用默认本地地址运行。部署前检查迁移、目录图片与 API 配置；部署后检查 `/healthz`、首页目录、投稿审核及图片访问。不要删除持久化的 MySQL、上传文件和备份目录。
