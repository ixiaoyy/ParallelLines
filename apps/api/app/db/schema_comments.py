from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import MetaData

COMMON_COLUMN_COMMENTS: dict[str, str] = {
    "id": "主键 UUID。",
    "created_at": "记录创建时间（UTC）。",
    "updated_at": "记录最后更新时间（UTC）。",
    "deleted_at": "软删除时间；为空表示未删除。",
    "user_id": "关联用户 ID。",
    "board_id": "关联版块 ID。",
    "topic_id": "关联主题 ID。",
    "post_id": "关联帖子 ID。",
    "target_type": "目标对象类型。",
    "target_id": "目标对象 ID。",
    "type": "业务类型。",
    "status": "当前状态。",
    "slug": "URL 友好的唯一标识。",
    "name": "显示名称。",
}

TABLE_COMMENTS: dict[str, str] = {
    "users": "用户账号、权限角色与账号状态。",
    "boards": "论坛版块/分类及版块统计计数。",
    "board_members": "版块成员、角色与通知订阅级别。",
    "tags": "主题标签及标签使用计数。",
    "topics": "论坛主题主表，保存主题状态、计数与排序信号。",
    "topic_tags": "主题与标签的多对多关联表。",
    "posts": "主题内帖子/楼层内容，保存原始 Markdown 与安全 HTML。",
    "topic_reads": "用户对主题的阅读进度与主题通知级别。",
    "reactions": "用户对主题或帖子的点赞等表态记录。",
    "bookmarks": "用户收藏的主题或帖子。",
    "notifications": "通知中心消息及阅读状态。",
    "flags": "内容举报、处理状态与处理结果。",
    "audit_logs": "审核与管理操作审计日志。",
}

COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "users": {
        "username": "登录名和公开显示用户名，唯一。",
        "email": "账号邮箱，唯一。",
        "hashed_password": "哈希后的登录密码。",
        "avatar_url": "用户头像 URL。",
        "role": "用户角色：普通用户、版主或管理员。",
        "status": "账号状态：正常、禁言、封禁或删除。",
        "last_seen_at": "用户最后活跃时间。",
    },
    "boards": {
        "slug": "版块 URL 标识，唯一。",
        "name": "版块名称。",
        "description": "版块说明与讨论范围。",
        "color": "版块主题色。",
        "avatar_url": "版块头像 URL。",
        "owner_id": "版块拥有者用户 ID；为空表示系统拥有。",
        "visibility": "版块可见性：公开、私密或不列出。",
        "topic_count": "版块下未删除主题数量缓存。",
        "post_count": "版块下帖子数量缓存。",
        "follower_count": "关注/订阅该版块的用户数量缓存。",
    },
    "board_members": {
        "board_id": "所属版块 ID。",
        "user_id": "成员用户 ID。",
        "role": "成员在版块内的角色。",
        "notification_level": "该成员对版块的通知级别。",
        "joined_at": "加入或关注版块时间。",
    },
    "tags": {
        "name": "标签名称，唯一。",
        "slug": "标签 URL 标识，唯一。",
        "topic_count": "使用该标签的主题数量缓存。",
    },
    "topics": {
        "board_id": "主题所属版块 ID。",
        "user_id": "主题作者用户 ID。",
        "title": "主题标题。",
        "slug": "主题 URL 标识，在同一版块内唯一。",
        "status": "主题状态：开放、关闭、归档或隐藏。",
        "pinned": "是否置顶主题。",
        "featured": "是否标记为精选/高信号主题。",
        "view_count": "主题浏览次数缓存。",
        "reply_count": "主题回复数量缓存。",
        "like_count": "主题点赞数量缓存。",
        "hot_score": "主题热度分，用于热榜排序。",
        "last_posted_at": "最后发帖或回复时间。",
        "deleted_at": "主题软删除时间；为空表示未删除。",
    },
    "topic_tags": {
        "topic_id": "主题 ID。",
        "tag_id": "标签 ID。",
    },
    "posts": {
        "topic_id": "帖子所属主题 ID。",
        "user_id": "发帖用户 ID。",
        "parent_id": "父帖子 ID，用于楼中楼/引用回复。",
        "post_number": "主题内楼层编号。",
        "raw_md": "用户提交的原始 Markdown 内容。",
        "cooked_html": "服务端渲染/清洗后的 HTML 内容。",
        "reply_count": "该帖子的直接回复数量缓存。",
        "like_count": "该帖子的点赞数量缓存。",
        "deleted_at": "帖子软删除时间；为空表示未删除。",
    },
    "topic_reads": {
        "topic_id": "主题 ID。",
        "user_id": "用户 ID。",
        "last_read_post_number": "用户已读到的最高楼层编号。",
        "notification_level": "用户对该主题的通知级别。",
    },
    "reactions": {
        "target_type": "表态目标类型：主题或帖子。",
        "target_id": "表态目标 ID。",
        "user_id": "发起表态的用户 ID。",
        "type": "表态类型，目前为点赞。",
    },
    "bookmarks": {
        "target_type": "收藏目标类型：主题或帖子。",
        "target_id": "收藏目标 ID。",
        "user_id": "收藏用户 ID。",
    },
    "notifications": {
        "user_id": "接收通知的用户 ID。",
        "type": "通知类型。",
        "topic_id": "关联主题 ID。",
        "post_id": "关联帖子 ID。",
        "actor_id": "触发通知的用户 ID。",
        "data": "通知展示所需的结构化扩展数据。",
        "read_at": "通知被读取的时间；为空表示未读。",
    },
    "flags": {
        "target_type": "被举报目标类型：主题或帖子。",
        "target_id": "被举报目标 ID。",
        "board_id": "举报内容所属版块 ID。",
        "reporter_id": "举报人用户 ID。",
        "reason": "举报原因。",
        "detail": "举报补充说明。",
        "status": "举报处理状态。",
        "resolution_note": "处理结论说明。",
        "resolved_by_id": "处理该举报的管理员/版主用户 ID。",
        "resolved_at": "举报处理完成时间。",
    },
    "audit_logs": {
        "actor_id": "执行操作的管理员/版主用户 ID。",
        "action": "审计动作类型。",
        "target_type": "被操作目标类型。",
        "target_id": "被操作目标 ID。",
        "board_id": "相关版块 ID。",
        "data": "动作上下文和变更前后的结构化数据。",
        "created_at": "审计日志记录时间（UTC）。",
    },
}


def column_comment(table_name: str, column_name: str) -> str | None:
    return COLUMN_COMMENTS.get(table_name, {}).get(column_name) or COMMON_COLUMN_COMMENTS.get(
        column_name
    )


def iter_column_comments(table_name: str) -> Mapping[str, str]:
    comments: dict[str, str] = {}
    for column_name, comment in COMMON_COLUMN_COMMENTS.items():
        comments[column_name] = comment
    comments.update(COLUMN_COMMENTS.get(table_name, {}))
    return comments


def apply_schema_comments(metadata: MetaData) -> None:
    for table_name, table in metadata.tables.items():
        if table_name in TABLE_COMMENTS:
            table.comment = TABLE_COMMENTS[table_name]
        for column in table.columns:
            comment = column_comment(table_name, column.name)
            if comment:
                column.comment = comment
