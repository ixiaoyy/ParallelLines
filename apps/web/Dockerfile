# syntax=docker/dockerfile:1
FROM node:22-alpine AS build

WORKDIR /repo

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
# 持久构建器可在锁变化时复用下载缓存；临时 CI runner 仍依赖已有的安装层缓存。
RUN --mount=type=cache,id=parallellines-pnpm-11,target=/pnpm/store \
    pnpm install --filter @parallellines/web... --frozen-lockfile --store-dir=/pnpm/store

COPY apps/web apps/web

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_STATIC_ASSET_BASE_URL=https://img.pingxingxian.space/static/web
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_STATIC_ASSET_BASE_URL=$VITE_STATIC_ASSET_BASE_URL

RUN pnpm --dir apps/web build

FROM nginx:1.27-alpine

ARG SOURCE_REVISION
LABEL org.opencontainers.image.revision=$SOURCE_REVISION

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html

EXPOSE 80
