#!/usr/bin/env bash
set -euo pipefail
revision=${1:?Release commit is required}
cd /opt/parallellines
test "$(git rev-parse origin/main)" = "$revision"
git diff --quiet
git diff --cached --quiet
git merge-base --is-ancestor HEAD "$revision"
git merge --ff-only "$revision"

# Do not activate against a previous API image if the normal scoped deploy has failed.
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml exec -T api python -c 'from app.main import create_app; paths = create_app().openapi()["paths"]; assert all("/api/v1/auth/chat-sso/" + name in paths for name in ("approve", "revoke")); print("[chat-sso] main API routes present")' < /dev/null

# Exactly the approved five OIDC groups. Existing unrelated environment bytes stay opaque.
test -s deploy/librechat/.env
test -s apps/api/.env
sudo docker run --rm --network none --user "$(id -u):$(id -g)" \
  -v "$PWD/deploy/librechat:/integration" --entrypoint node \
  registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5 \
  /integration/configure-models.cjs
sudo docker run --rm --network none --user 0:0 \
  -v "$PWD:/workspace" --entrypoint node \
  registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5 \
  /workspace/deploy/librechat/initialize-sso.cjs /workspace

export CHAT_SSO_RELEASE="$revision"
cd deploy/librechat
# Non-secret immutable client revision retained for later chat operations.
session_env=()
if test -f .runtime/session-release.env; then
  session_env=(--env-file .runtime/session-release.env)
fi
chat=(sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env "${session_env[@]}" -f compose.production.yaml -f compose.sso.yaml)
"${chat[@]}" config --quiet
"${chat[@]}" up -d --build --wait --wait-timeout 180 --no-deps chat-oidc

# Main SSO API is already enabled; this chat-only update does not restart the main API.
"${chat[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 240 librechat
"${chat[@]}" exec -T librechat node -e '
  const fs = require("node:fs");
  const base = JSON.parse(fs.readFileSync("/app/data/family-config/librechat.yaml", "utf8"));
  const approved = JSON.parse(fs.readFileSync("/app/data/family-config/approved-user-profile.yaml", "utf8"));
  const empty = base.endpoints.openAI.models.length === 0;
  const candidates = base.modelSpecs.list.map(spec => spec.preset.model);
  const menu = JSON.stringify(candidates) === JSON.stringify(["gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol"]);
  const keyLoaded = Boolean((process.env.OPENAI_API_KEY || "").trim());
  const ok = empty && menu && keyLoaded && base.balance.enabled === true && base.modelSpecs.list[0].default === true && process.env.SSO_REQUIRED === "true" && process.env.ALLOW_REGISTRATION === "false" && process.env.ALLOW_EMAIL_LOGIN === "false";
  console.log(JSON.stringify({ ssoRequired: true, emailLogin: false, registration: false, defaultModelGrants: false, candidates, defaultModel: candidates[0], runtimeKeyLoaded: keyLoaded, grantTemplateReady: approved.endpoints.openAI.models.length > 0, serverBalanceChecks: base.balance.enabled === true, verified: ok }));
  if (!ok) process.exit(1);
' < /dev/null
"${chat[@]}" exec -T librechat node /integration/sso/verify-public.cjs < /dev/null
"${chat[@]}" ps librechat chat-oidc
echo '[chat-sso] public checks passed; no model request or account permission update performed'
