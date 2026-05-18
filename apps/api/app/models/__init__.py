from app.db.base import Base
from app.db.schema_comments import apply_schema_comments
from app.models.forum import Board, BoardMember, Post, Tag, Topic, TopicRead, topic_tags
from app.models.interaction import Bookmark, Notification, Reaction
from app.models.moderation import AuditLog, Flag
from app.models.user import User

apply_schema_comments(Base.metadata)

__all__ = [
    "AuditLog",
    "Board",
    "BoardMember",
    "Bookmark",
    "Flag",
    "Notification",
    "Post",
    "Reaction",
    "Tag",
    "Topic",
    "TopicRead",
    "User",
    "topic_tags",
]
