FROM node:22-alpine AS build

WORKDIR /repo

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --filter @parallellines/web... --frozen-lockfile

COPY apps/web apps/web

ARG VITE_API_BASE_URL=/api/v1
ARG VITE_STATIC_ASSET_BASE_URL=https://img.pingxingxian.space/static/web
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_STATIC_ASSET_BASE_URL=$VITE_STATIC_ASSET_BASE_URL

RUN pnpm --dir apps/web build

FROM nginx:1.27-alpine

COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/apps/web/dist /usr/share/nginx/html

EXPOSE 80
