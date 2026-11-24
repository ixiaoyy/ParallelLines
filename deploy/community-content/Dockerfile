ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# 生产使用已核实的现用 API 镜像为基底，只覆盖本项文件，不携带其他工作区变更。
COPY app/core/community_content.py /app/app/core/community_content.py
COPY app/services/community_schedule.py /app/app/services/community_schedule.py
COPY app/services/scheduled_content.py /app/app/services/scheduled_content.py
COPY app/services/overseas_content.py /app/app/services/overseas_content.py
COPY app/services/living_forum.py /app/app/services/living_forum.py
COPY app/services/daily_reading.py /app/app/services/daily_reading.py
COPY app/services/daily_reading_provider.py /app/app/services/daily_reading_provider.py
COPY app/workers/community_content.py /app/app/workers/community_content.py
COPY app/workers/community_content_health.py /app/app/workers/community_content_health.py
COPY scripts/collect_weibo_hot_search.py /app/scripts/collect_weibo_hot_search.py
COPY scripts/plan_living_forum_day.py /app/scripts/plan_living_forum_day.py
COPY scripts/publish_daily_reading.py /app/scripts/publish_daily_reading.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD ["python", "-m", "app.workers.community_content_health"]
CMD ["python", "-m", "app.workers.community_content"]
