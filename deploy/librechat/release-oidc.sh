#!/usr/bin/env bash
set -euo pipefail
revision=${1:?Release commit is required}
cd /opt/parallellines
test "$(git rev-parse origin/main)" = "$revision"
git diff --quiet
git diff --cached --quiet
git merge-base --is-ancestor HEAD "$revision"
git merge --ff-only "$revision"

# Existing trust materials stay in place. Only the OIDC provider is recreated.
cd deploy/librechat
# Non-secret immutable client revision retained for later chat operations.
session_env=()
if test -f .runtime/session-release.env; then
  session_env=(--env-file .runtime/session-release.env)
fi
test -s .env
test -s ../chat-sso/.env
test -s ../chat-sso/secrets/signing.jwks.json
export CHAT_SSO_RELEASE="$revision"
chat=(sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env "${session_env[@]}" -f compose.production.yaml -f compose.sso.yaml)
"${chat[@]}" config --quiet
"${chat[@]}" up -d --build --wait --wait-timeout 180 --no-deps chat-oidc
"${chat[@]}" exec -T chat-oidc node --input-type=module -e '
  const base = "http://127.0.0.1:3002";
  const metadata = await fetch(base + "/auth/oidc/.well-known/openid-configuration");
  if (!metadata.ok || (await metadata.json()).issuer !== "https://pingxingxian.space/auth/oidc") throw new Error("discovery_check_failed");
  const r = await fetch(base + "/auth/oidc/interaction/finish", {
    method: "POST", redirect: "manual",
    headers: { Origin: "https://pingxingxian.space", Accept: "text/html", "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ interaction_id: "synthetic-invalid-interaction", approval_code: "x".repeat(32) }),
  });
  const html = await r.text();
  const denied = r.status === 403 && r.headers.get("content-type")?.startsWith("text/html") && html.includes("href=\"/chat/\"") && !html.includes("synthetic-invalid-interaction");
  console.log(JSON.stringify({ discoveryValid: true, unauthenticatedRequestDenied: r.status === 403, safeRecoveryPage: denied, credentialsChanged: false, modelRequestSent: false }));
  if (!denied) process.exit(1);
' < /dev/null
"${chat[@]}" ps chat-oidc
echo '[chat-oidc] provider-only recovery update healthy; no account or credential changes'
