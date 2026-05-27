from app.db.base import Base
from app.db.schema_comments import apply_schema_comments
from app.models.admin import SiteSetting
from app.models.ai import AiTopicSummary
from app.models.background_job import BackgroundJob, BackgroundJobLog
from app.models.backup import BackupArtifact
from app.models.badge import BadgeDefinition, UserBadge, UserTrustLevelEvent
from app.models.draft import Draft
from app.models.email import EmailDeliveryEvent, InboundEmail, UserEmailPreference
from app.models.event import CalendarEvent, EventRsvp
from app.models.forum import (
    Board,
    BoardInvitation,
    BoardMember,
    Poll,
    PollOption,
    PollVote,
    Post,
    PostRevision,
    Tag,
    Topic,
    TopicRead,
    topic_tags,
)
from app.models.integration import (
    ApiKey,
    ExternalIntegration,
    ExternalIntegrationEvent,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.models.interaction import Bookmark, Notification, Reaction, Vote
from app.models.moderation import (
    AuditLog,
    Flag,
    RateLimitEvent,
    Reviewable,
    ReviewableEvent,
    ScreenedRule,
    SpamAction,
)
from app.models.push import PushSubscription
from app.models.search import SearchDocument, SearchLog
from app.models.social import PrivateMessageParticipant, UserRelationship
from app.models.upload import Upload
from app.models.user import (
    EmailVerificationCode,
    User,
    UserPointEvent,
    UserRecoveryCode,
    UserSecurityToken,
    UserSession,
)

apply_schema_comments(Base.metadata)

__all__ = [
    "AuditLog",
    "AiTopicSummary",
    "ApiKey",
    "BadgeDefinition",
    "BackupArtifact",
    "BackgroundJob",
    "BackgroundJobLog",
    "Board",
    "BoardInvitation",
    "BoardMember",
    "Bookmark",
    "CalendarEvent",
    "Draft",
    "EmailVerificationCode",
    "EmailDeliveryEvent",
    "EventRsvp",
    "ExternalIntegration",
    "ExternalIntegrationEvent",
    "Flag",
    "Notification",
    "InboundEmail",
    "Poll",
    "PollOption",
    "PollVote",
    "Vote",
    "WebhookDelivery",
    "WebhookEndpoint",
    "Post",
    "PostRevision",
    "PrivateMessageParticipant",
    "PushSubscription",
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
    "UserBadge",
    "UserRelationship",
    "UserPointEvent",
    "UserTrustLevelEvent",
    "UserEmailPreference",
    "UserRecoveryCode",
    "UserSecurityToken",
    "UserSession",
    "topic_tags",
]
