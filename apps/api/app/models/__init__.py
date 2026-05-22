from app.db.base import Base
from app.db.schema_comments import apply_schema_comments
from app.models.admin import SiteSetting
from app.models.background_job import BackgroundJob, BackgroundJobLog
from app.models.backup import BackupArtifact
from app.models.draft import Draft
from app.models.email import EmailDeliveryEvent, InboundEmail, UserEmailPreference
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
from app.models.moderation import (
    AuditLog,
    Flag,
    RateLimitEvent,
    Reviewable,
    ReviewableEvent,
    ScreenedRule,
    SpamAction,
)
from app.models.search import SearchDocument, SearchLog
from app.models.social import PrivateMessageParticipant, UserRelationship
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
    "BackupArtifact",
    "BackgroundJob",
    "BackgroundJobLog",
    "Board",
    "BoardInvitation",
    "BoardMember",
    "Bookmark",
    "Draft",
    "EmailVerificationCode",
    "EmailDeliveryEvent",
    "Flag",
    "Notification",
    "InboundEmail",
    "Post",
    "PostRevision",
    "PrivateMessageParticipant",
    "RateLimitEvent",
    "Reviewable",
    "ReviewableEvent",
    "Reaction",
    "ScreenedRule",
    "SearchDocument",
    "SearchLog",
    "SiteSetting",
    "SpamAction",
    "Tag",
    "Topic",
    "TopicRead",
    "Upload",
    "User",
    "UserRelationship",
    "UserEmailPreference",
    "UserRecoveryCode",
    "UserSecurityToken",
    "UserSession",
    "topic_tags",
]
