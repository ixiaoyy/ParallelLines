#!/bin/sh
set -eu

DOMAIN="pingxingxian.space"
REAL_CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
REAL_KEY="/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
FALLBACK_DIR="/etc/nginx/ssl/fallback"
ACTIVE_DIR="/etc/nginx/ssl/live"
FALLBACK_CERT="${FALLBACK_DIR}/fullchain.pem"
FALLBACK_KEY="${FALLBACK_DIR}/privkey.pem"
ACTIVE_CERT="${ACTIVE_DIR}/fullchain.pem"
ACTIVE_KEY="${ACTIVE_DIR}/privkey.pem"

activate_real_certificate() {
    # 拿锁后重新读当前链接，避免和主站发布的证书切换重复重载。
    [ -s "$REAL_CERT" ] && [ -s "$REAL_KEY" ] || return 0
    previous_cert=$(readlink "$ACTIVE_CERT") || return 1
    previous_key=$(readlink "$ACTIVE_KEY") || return 1
    if [ "$previous_cert" = "$REAL_CERT" ] && [ "$previous_key" = "$REAL_KEY" ]; then
        return 0
    fi
    if ! ln -sf "$REAL_CERT" "$ACTIVE_CERT" || ! ln -sf "$REAL_KEY" "$ACTIVE_KEY" ||
       ! nginx -t || ! nginx -s reload; then
        ln -sf "$previous_cert" "$ACTIVE_CERT" || return 1
        ln -sf "$previous_key" "$ACTIVE_KEY" || return 1
        return 1
    fi
}

activate_with_tls_lock() (
    # 基础 Compose 的本地入口不依赖工具站；生产只打开挂入的现有锁文件。
    if [ -n "${GATEWAY_TLS_LOCK_FILE:-}" ]; then
        [ -f "$GATEWAY_TLS_LOCK_FILE" ] && [ ! -L "$GATEWAY_TLS_LOCK_FILE" ] || exit 1
        exec 9< "$GATEWAY_TLS_LOCK_FILE"
        flock -n -E 75 9 || exit "$?"
    fi
    activate_real_certificate
)

mkdir -p "${FALLBACK_DIR}" "${ACTIVE_DIR}"

if [ ! -s "${FALLBACK_CERT}" ] || [ ! -s "${FALLBACK_KEY}" ]; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "${FALLBACK_KEY}" \
        -out "${FALLBACK_CERT}" \
        -subj "/CN=${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN},DNS:www.${DOMAIN}"
fi

if [ -s "${REAL_CERT}" ] && [ -s "${REAL_KEY}" ]; then
    ln -sf "${REAL_CERT}" "${ACTIVE_CERT}"
    ln -sf "${REAL_KEY}" "${ACTIVE_KEY}"
else
    ln -sf "${FALLBACK_CERT}" "${ACTIVE_CERT}"
    ln -sf "${FALLBACK_KEY}" "${ACTIVE_KEY}"
fi

# 仅补初签后的链接切换；守望循环争锁时保持现有 Nginx，下一轮再试。
(
    while :; do
        sleep 60
        if [ -s "$REAL_CERT" ] && [ -s "$REAL_KEY" ] &&
           { [ "$(readlink "$ACTIVE_CERT")" != "$REAL_CERT" ] ||
             [ "$(readlink "$ACTIVE_KEY")" != "$REAL_KEY" ]; }; then
            status=0
            activate_with_tls_lock || status=$?
            case "$status" in
                0|75) ;;
                *) echo "[nginx] TLS activation deferred: lock or reload failed" >&2 ;;
            esac
        fi
    done
) &

exec nginx -g "daemon off;"
