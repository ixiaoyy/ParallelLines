from app.db.base import Base
from app.db.schema_comments import apply_schema_comments
from app.models.forum import (
    Board,
    BoardInvitation,
    BoardMember,
    Post,
    PostRevision,
    Tag,
    Topic,
    TopicRead,
    topic_tags,
)
from app.models.interaction import Bookmark, Notification, Reaction
from app.models.moderation import AuditLog, Flag, RateLimitEvent, ScreenedRule, SpamAction
from app.models.upload import Upload
from app.models.user import (
    EmailVerificationCode,
    User,
    UserRecoveryCode,
    UserSecurityToken,
    UserSession,
)

apply_schema_comments(Base.metadata)

__all__ = [
    "AuditLog",
    "Board",
    "BoardInvitation",
    "BoardMember",
    "Bookmark",
    "EmailVerificationCode",
    "Flag",
    "Notification",
    "Post",
    "PostRevision",
    "RateLimitEvent",
    "Reaction",
    "ScreenedRule",
    "SpamAction",
    "Tag",
    "Topic",
    "TopicRead",
    "Upload",
    "User",
    "UserRecoveryCode",
    "UserSecurityToken",
    "UserSession",
    "topic_tags",
]
