#!/usr/bin/env bash
set -euo pipefail

mode=${1:-preflight}
revision=${2:?Release commit is required}
initialize=${3:-false}
cd /opt/parallellines
test "$mode" = preflight || test "$mode" = deploy || test "$mode" = models
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
git merge-base --is-ancestor HEAD "$revision"
# Fast-forward merge refuses conflicting tracked/untracked files; never hard-reset local work.
git merge --ff-only "$revision"
cd deploy/librechat
if test "$mode" = models; then
  # This mode never initializes credentials, reads their values, or grants profiles.
  test -f .env
  active_files=$(sudo docker inspect parallellines-chat-librechat-1 --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}')
  if test "$active_files" != "$PWD/compose.production.yaml,$PWD/compose.disabled.yaml" && \
     test "$active_files" != "$PWD/compose.production.yaml,$PWD/compose.disabled.yaml,$PWD/compose.sso.yaml"; then
    echo '[chat] stopped before editing: existing deployment mode changed; no Key or model settings changed'
    exit 3
  fi
  sudo docker run --rm --network none --user "$(id -u):$(id -g)" \
    -v "$PWD:/integration" --entrypoint node \
    registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5 \
    /integration/configure-models.cjs
  model_compose=(sudo docker compose --env-file .env -f compose.production.yaml -f compose.disabled.yaml)
  if test "$active_files" = "$PWD/compose.production.yaml,$PWD/compose.disabled.yaml,$PWD/compose.sso.yaml"; then
    export CHAT_SSO_RELEASE="$revision"
    model_compose=(sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml)
  fi
  "${model_compose[@]}" config --quiet
  "${model_compose[@]}" up -d --wait --wait-timeout 240 --no-deps --force-recreate librechat
  "${model_compose[@]}" exec -T librechat node -e '
    const fs = require("node:fs");
    const dir = "/app/data/family-config/";
    const selected = JSON.parse(fs.readFileSync(dir + "selected-models.json", "utf8"));
    const base = JSON.parse(fs.readFileSync(dir + "librechat.yaml", "utf8"));
    const profile = JSON.parse(fs.readFileSync(dir + "approved-user-profile.yaml", "utf8"));
    const ids = selected.models.map(m => m.id);
    const baseEmpty = base.endpoints.openAI.models.length === 0;
    const menuMatches = JSON.stringify(base.modelSpecs.list.map(spec => spec.preset.model)) === JSON.stringify(ids);
    const templateEmpty = profile.endpoints.openAI.models.length === 0;
    const ok = JSON.stringify(ids) === JSON.stringify(["gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol"]) &&
      process.env.OPENAI_CHAT_MODELS === ids.join(",") && baseEmpty && templateEmpty && menuMatches;
    console.log(JSON.stringify({ selectedModels: selected.models, runtimeModelSetting: process.env.OPENAI_CHAT_MODELS,
      defaultAccountAccess: false, baseModelsEmpty: baseEmpty, grantTemplateModelsEmpty: templateEmpty, verified: ok }));
    if (!ok) process.exit(1);
  ' < /dev/null
  "${model_compose[@]}" ps librechat
  echo '[chat] model candidates configured; API Key and account/profile records not changed'
  exit 0
fi
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
chat_compose=(sudo docker compose --env-file .env -f compose.production.yaml -f compose.disabled.yaml)
"${chat_compose[@]}" config --quiet
"${chat_compose[@]}" pull
"${chat_compose[@]}" up -d --wait --wait-timeout 240

# Only generated secret-free config is inspected. This release must remain disabled.
"${chat_compose[@]}" exec -T librechat node -e '
  const fs = require("node:fs");
  const c = JSON.parse(fs.readFileSync("/app/data/family-config/librechat.yaml", "utf8"));
  const p = JSON.parse(fs.readFileSync("/app/data/family-config/approved-user-profile.yaml", "utf8"));
  const base = c.endpoints?.openAI?.models || [];
  const selected = p.endpoints?.openAI?.models || [];
  const disabled = base.length === 0 && selected.length === 0;
  console.log(JSON.stringify({ disabled, defaultAccountAccess: false, baseModels: base, configuredModels: selected, welcome: c.interface?.customWelcome }));
  if (!disabled) process.exit(1);
' < /dev/null
"${chat_compose[@]}" ps
echo '[chat] healthy disabled service started; public proxy is activated separately after health verification'
