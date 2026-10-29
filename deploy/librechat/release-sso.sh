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
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml exec -T api python -c 'from app.main import create_app; paths = create_app().openapi()["paths"]; assert all("/api/v1/auth/chat-sso/" + name in paths for name in ("approve", "revoke")); print("[chat-sso] main API routes present")'

# Exactly the approved five OIDC groups. Existing unrelated environment bytes stay opaque.
test -s deploy/librechat/.env
test -s apps/api/.env
sudo docker run --rm --network none --user 0:0 \
  -v "$PWD:/workspace" --entrypoint node \
  registry.librechat.ai/librechat-ai/librechat-api@sha256:e95924ac84c0abf6f9e69f1f59e781379201a2cc9495910e22f2687e25f3c2a5 \
  /workspace/deploy/librechat/initialize-sso.cjs /workspace

export CHAT_SSO_RELEASE="$revision"
cd deploy/librechat
chat=(sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env -f compose.production.yaml -f compose.disabled.yaml -f compose.sso.yaml)
"${chat[@]}" config --quiet
"${chat[@]}" up -d --build --wait --wait-timeout 180 --no-deps chat-oidc

# The main API source/image was deployed by the scoped normal pipeline. Reload only its env.
cd /opt/parallellines
sudo docker compose -f docker-compose.yml -f deploy/docker-compose.migration.yml up -d --no-build --no-deps --force-recreate --wait --wait-timeout 180 api
cd deploy/librechat
"${chat[@]}" up -d --no-deps --force-recreate --wait --wait-timeout 240 librechat
"${chat[@]}" exec -T librechat node -e '
  const fs = require("node:fs");
  const base = JSON.parse(fs.readFileSync("/app/data/family-config/librechat.yaml", "utf8"));
  const approved = JSON.parse(fs.readFileSync("/app/data/family-config/approved-user-profile.yaml", "utf8"));
  const empty = base.endpoints.openAI.models.length === 0 && approved.endpoints.openAI.models.length === 0;
  const ok = empty && process.env.OPENAI_API_KEY === "" && process.env.SSO_REQUIRED === "true" && process.env.ALLOW_REGISTRATION === "false" && process.env.ALLOW_EMAIL_LOGIN === "false";
  console.log(JSON.stringify({ ssoRequired: true, emailLogin: false, registration: false, defaultModelGrants: false, gptDisabled: empty, verified: ok }));
  if (!ok) process.exit(1);
'
"${chat[@]}" exec -T librechat node /integration/sso/verify-public.cjs
"${chat[@]}" ps librechat chat-oidc
echo '[chat-sso] public checks passed; no model request or account permission update performed'
