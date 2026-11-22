#!/bin/sh
# 在各发布路径中接续论坛启用状态；本文件只被 source，不替代独立论坛发布。
select_parallellines_compose_files() {
    COMPOSE_FILES="-f docker-compose.yml -f deploy/docker-compose.migration.yml"
    FORUM_ENABLED=false
    test -f deploy/docker-compose.migration.yml || return 1

    # 标记只保存已经交付的论坛镜像标签，不执行文件内容，也不自动构建另一个版本。
    if test -e .deployment/forum-enabled; then
        test -f .deployment/forum-enabled || {
            echo "[deploy] forum-enabled must be a regular image-tag file" >&2
            return 1
        }
        FORUM_IMAGE_TAG=$(cat .deployment/forum-enabled)
        case "$FORUM_IMAGE_TAG" in
            ""|*[!A-Za-z0-9_.-]*|[.-]*)
                echo "[deploy] forum-enabled contains an invalid image tag" >&2
                return 1
                ;;
        esac
        if test "${#FORUM_IMAGE_TAG}" -gt 128; then
            echo "[deploy] forum image tag exceeds 128 characters" >&2
            return 1
        fi
        for recipe in docker-compose.forum.yml deploy/nginx/forum.conf deploy/nginx/forum-main-redirects.conf; do
            test -s "$recipe" || {
                echo "[deploy] enabled forum is missing recipe: $recipe" >&2
                return 1
            }
        done
        # 缺证书或已发布镜像时明确停止，不退回会丢失论坛入口的基础 Compose。
        for certificate in fullchain.pem privkey.pem; do
            sudo test -s "/opt/parallellines/var/letsencrypt/live/forum.pingxingxian.space/$certificate" || {
                echo "[deploy] enabled forum certificate is missing: $certificate" >&2
                return 1
            }
        done
        sudo docker image inspect "parallellines-forum-web:$FORUM_IMAGE_TAG" >/dev/null || {
            echo "[deploy] enabled forum image is not loaded" >&2
            return 1
        }
        export FORUM_IMAGE_TAG
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.forum.yml"
        FORUM_ENABLED=true
    fi

    # 后续主站/API发布必须接续已启用的统一登录，不能因默认关闭而恢复子站密码入口。
    if test -e .deployment/unified-auth-enabled; then
        test -f .deployment/unified-auth-enabled && test -s docker-compose.unified.yml || {
            echo "[deploy] unified login marker or recipe is invalid" >&2
            return 1
        }
        UNIFIED_AUTH_RELEASE=$(cat .deployment/unified-auth-enabled)
        case "$UNIFIED_AUTH_RELEASE" in
            ""|*[!A-Za-z0-9_.-]*|[.-]*)
                echo "[deploy] unified login release marker is invalid" >&2
                return 1
                ;;
        esac
        if test "${#UNIFIED_AUTH_RELEASE}" -gt 128 || test "$FORUM_ENABLED" != true; then
            echo "[deploy] unified login requires the existing enabled circle site" >&2
            return 1
        fi
        export VITE_UNIFIED_AUTH_ENABLED=true
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.unified.yml"
    fi

    # 共享网关持久站点扩展（优先持久化原依赖容器层的 Tavern / Matrix 路由，不搬动已持久化站点）。
    if test -e .deployment/gateway-sites-enabled; then
        test -f .deployment/gateway-sites-enabled || {
            echo "[deploy] gateway-sites-enabled must be a regular marker file" >&2
            return 1
        }
        for recipe in docker-compose.gateway-sites.yml deploy/nginx/sites.d/00-include-sites.conf deploy/nginx/sites.d/verify-gateway-sites.mjs; do
            test -s "$recipe" || {
                echo "[deploy] enabled gateway sites overlay is missing recipe: $recipe" >&2
                return 1
            }
        done
        GATEWAY_SITES_TARGET="${GATEWAY_SITES_DIR:-/opt/parallellines/nginx/sites.d}"
        test -d "$GATEWAY_SITES_TARGET" || {
            echo "[deploy] enabled gateway sites directory is missing: $GATEWAY_SITES_TARGET" >&2
            return 1
        }
        command -v node >/dev/null 2>&1 || {
            echo "[deploy] node is required to verify enabled gateway sites before loading" >&2
            return 1
        }
        node deploy/nginx/sites.d/verify-gateway-sites.mjs "$GATEWAY_SITES_TARGET" deploy/nginx/sites.d/00-include-sites.conf >/dev/null || {
            echo "[deploy] gateway sites preflight verification failed" >&2
            return 1
        }
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gateway-sites.yml"
    fi
}

select_parallellines_compose_files
