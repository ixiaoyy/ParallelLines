FROM node:22-alpine

WORKDIR /repo

RUN corepack enable

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --filter @parallellines/web... --frozen-lockfile

COPY apps/web apps/web

ARG VITE_API_BASE_URL=http://localhost:8000/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN pnpm --dir apps/web build

EXPOSE 5173

CMD ["pnpm", "--dir", "apps/web", "preview", "--host", "0.0.0.0", "--port", "5173"]
