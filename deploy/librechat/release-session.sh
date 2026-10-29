#!/usr/bin/env bash
set -euo pipefail
revision=${1:?Release commit is required}
bundle_sha=${2:?Runner bundle SHA256 is required}
[[ "$revision" =~ ^[0-9a-f]{40}$ ]]
[[ "$bundle_sha" =~ ^[0-9a-f]{64}$ ]]
cd /opt/parallellines
test "$(git rev-parse origin/main)" = "$revision"
git diff --quiet
git diff --cached --quiet
git merge-base --is-ancestor HEAD "$revision"
git merge --ff-only "$revision"
cd deploy/librechat

# Existing runtime credentials remain opaque to this script. No initialization,
# model/account changes, server build, provider build, or image pull is performed.
test -f .env
test -f ../chat-sso/.env
test -d .runtime
test ! -L .runtime
exec 9>.runtime/native-session.lock
flock -n 9

# Use the already-running provider's exact image tag in the merged Compose config.
# Passing the new revision here would suggest a new provider image to Compose.
mapfile -t oidc_ids < <(sudo docker ps -q \
  --filter label=com.docker.compose.project=parallellines-chat \
  --filter label=com.docker.compose.service=chat-oidc)
test "${#oidc_ids[@]}" -eq 1
oidc_id=${oidc_ids[0]}
test "$(sudo docker inspect "$oidc_id" --format '{{.State.Running}} {{.State.Health.Status}}')" = 'true healthy'
oidc_image=$(sudo docker inspect "$oidc_id" --format '{{.Config.Image}}')
[[ "$oidc_image" =~ ^parallellines-chat-oidc:([0-9a-f]{40})$ ]]
export CHAT_SSO_RELEASE=${BASH_REMATCH[1]}

python3 ./install-native-client.py \
  "$PWD/.runtime/incoming/native-session-${revision}.tar" "$bundle_sha"
chat=(sudo --preserve-env=CHAT_SSO_RELEASE docker compose --env-file .env --env-file ../chat-sso/.env --env-file .runtime/session-release.env -f compose.production.yaml -f compose.sso.yaml)
"${chat[@]}" config --quiet
"${chat[@]}" up -d --no-deps --force-recreate --pull never --wait --wait-timeout 240 librechat
test "$(sudo docker inspect "$oidc_id" --format '{{.State.Running}} {{.State.Health.Status}}')" = 'true healthy'
test "$(sudo docker inspect "$oidc_id" --format '{{.Config.Image}}')" = "$oidc_image"
"${chat[@]}" ps librechat chat-oidc
echo '[chat-session] verified native client mounted; only librechat recreated, no credential/account/model changes'
