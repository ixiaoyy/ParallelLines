#!/usr/bin/env bash
set -euo pipefail
revision=${1:?Release commit is required}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
cd /opt/parallellines
test "$(git rev-parse origin/main)" = "$revision"
git diff --quiet
git diff --cached --quiet
git merge-base --is-ancestor HEAD "$revision"
git merge --ff-only "$revision"
cd deploy/librechat
test -f .env
test -f ../chat-sso/.env
test -f .runtime/session-release.env

# Keep the healthy provider and already verified immutable native client.
mapfile -t oidc_ids < <(sudo docker ps -q \
  --filter label=com.docker.compose.project=parallellines-chat \
  --filter label=com.docker.compose.service=chat-oidc)
test "${#oidc_ids[@]}" -eq 1
oidc_id=${oidc_ids[0]}
test "$(sudo docker inspect "$oidc_id" --format '{{.State.Running}} {{.State.Health.Status}}')" = 'true healthy'
oidc_image=$(sudo docker inspect "$oidc_id" --format '{{.Config.Image}}')
[[ "$oidc_image" =~ ^parallellines-chat-oidc:([0-9a-f]{40})$ ]]
export CHAT_SSO_RELEASE=${BASH_REMATCH[1]}
chat=(sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env --env-file .runtime/session-release.env -f compose.production.yaml -f compose.sso.yaml)
"${chat[@]}" config --quiet
"${chat[@]}" up -d --no-deps --force-recreate --pull never --wait --wait-timeout 240 librechat
test "$(sudo docker inspect "$oidc_id" --format '{{.State.Running}} {{.State.Health.Status}}')" = 'true healthy'
test "$(sudo docker inspect "$oidc_id" --format '{{.Config.Image}}')" = "$oidc_image"
"${chat[@]}" ps librechat chat-oidc
echo '[chat-runtime] only LibreChat recreated; verified client, provider, credentials and account settings preserved'
