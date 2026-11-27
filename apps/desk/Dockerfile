# syntax=docker/dockerfile:1
FROM node:22-alpine AS build

WORKDIR /desk
RUN corepack enable && corepack prepare pnpm@11.1.1 --activate

COPY apps/desk/package.json apps/desk/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=parallellines-desk-pnpm-11,target=/pnpm/store \
    pnpm install --store-dir=/pnpm/store

COPY apps/desk ./
ARG VITE_DESK_BASE=/desk/
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_DESK_BASE=$VITE_DESK_BASE
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN pnpm run build

FROM nginx:1.27-alpine
ARG SOURCE_REVISION
LABEL org.opencontainers.image.revision=$SOURCE_REVISION

# 静态容器不持有证书、账号或数据库；通过共享网关挂载至 pingxingxian.space/desk 或根首页。
COPY apps/desk/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /desk/dist-desk /usr/share/nginx/html
EXPOSE 80
