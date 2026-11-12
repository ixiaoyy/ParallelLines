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
}

select_parallellines_compose_files
