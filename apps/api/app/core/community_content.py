from datetime import datetime

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommunityContentSettings(BaseSettings):
    """独立内容 worker 的显式启用门；不改变旧后台或历史开关。"""

    enabled: bool = False
    start_at: datetime | None = None
    model_config = SettingsConfigDict(
        env_prefix="COMMUNITY_CONTENT_", env_file=".env", extra="ignore"
    )

    @model_validator(mode="after")
    def require_activation_time(self) -> "CommunityContentSettings":
        """启用时必须给出带时区的激活水位，避免重启后补发历史时段。"""

        if self.enabled and (
            self.start_at is None
            or self.start_at.tzinfo is None
            or self.start_at.utcoffset() is None
        ):
            raise ValueError("COMMUNITY_CONTENT_START_AT must be timezone-aware when enabled")
        return self
