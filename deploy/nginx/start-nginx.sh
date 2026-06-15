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

# Switches from the temporary fallback certificate to the real Let's Encrypt
# certificate after Certbot writes it. Side effect: reloads Nginx in place.
(
    while :; do
        sleep 60
        if [ -s "${REAL_CERT}" ] && [ -s "${REAL_KEY}" ] && [ "$(readlink "${ACTIVE_CERT}")" != "${REAL_CERT}" ]; then
            ln -sf "${REAL_CERT}" "${ACTIVE_CERT}"
            ln -sf "${REAL_KEY}" "${ACTIVE_KEY}"
            nginx -s reload || true
        fi
    done
) &

exec nginx -g "daemon off;"
