"""独立轻量健康探针；不导入 ORM、运行配置或建立数据库连接。"""

from datetime import UTC, datetime
from pathlib import Path

HEARTBEAT = Path("/tmp/parallellines-community-content-heartbeat")


def worker_is_healthy() -> bool:
    """仅核对最近五分钟完成的轮询时间；缺失、无效、过期或未来心跳均失败。"""

    try:
        seen = datetime.fromisoformat(HEARTBEAT.read_text(encoding="ascii"))
        return 0 <= (datetime.now(UTC) - seen).total_seconds() < 300
    except (OSError, ValueError, TypeError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if worker_is_healthy() else 1)
