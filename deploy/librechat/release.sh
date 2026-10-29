#!/usr/bin/env bash
set -euo pipefail

mode=${1:-preflight}
revision=${2:?Release commit is required}
initialize=${3:-false}
cd /opt/parallellines
test "$mode" = preflight || test "$mode" = deploy
test "$(git rev-parse origin/main)" = "$revision"

# Report capacity and state without reading application environments or credentials.
echo '[chat] preflight: memory and storage'
free -m
df -h / /data
sudo docker system df
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
sudo docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
sudo docker network inspect parallellines_default --format 'network={{.Name}} internal={{.Internal}}'
if test -e deploy/librechat/.env; then
  echo '[chat] existing server-local .env present; contents not inspected'
else
  echo '[chat] server-local .env absent; approved initialization or owner setup required'
fi
test "$mode" != preflight || exit 0

# Preserve unrelated server modifications and never move an advanced main backwards.
git diff --quiet
git diff --cached --quiet
test "$(git rev-parse origin/main)" = "$revision"
git reset --hard "$revision"
cd deploy/librechat
if ! test -e .env; then
  if test "$initialize" != true; then
    echo '[chat] stopped before startup: application-secret initialization not authorized'
    exit 3
  fi
  api_image=registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5
  sudo docker pull "$api_image"
  sudo docker run --rm --network none --user "$(id -u):$(id -g)" \
    -v "$PWD:/integration" --entrypoint node "$api_image" /integration/init.cjs
  chmod 600 .env
fi
sudo docker compose --env-file .env -f compose.production.yaml config --quiet
sudo docker compose --env-file .env -f compose.production.yaml pull
sudo docker compose --env-file .env -f compose.production.yaml up -d --wait --wait-timeout 240

# Only generated secret-free config is inspected. This release must remain disabled.
sudo docker compose --env-file .env -f compose.production.yaml exec -T librechat node -e '
  const fs = require("node:fs");
  const c = JSON.parse(fs.readFileSync("/app/data/family-config/librechat.yaml", "utf8"));
  const p = JSON.parse(fs.readFileSync("/app/data/family-config/approved-user-profile.yaml", "utf8"));
  const base = c.endpoints?.openAI?.models || [];
  const selected = p.endpoints?.openAI?.models || [];
  const disabled = base.length === 0 && selected.length === 0;
  console.log(JSON.stringify({ disabled, defaultAccountAccess: false, baseModels: base, configuredModels: selected, welcome: c.interface?.customWelcome }));
  if (!disabled) process.exit(1);
'
sudo docker compose --env-file .env -f compose.production.yaml ps
echo '[chat] healthy disabled service started; public proxy is activated separately after health verification'
