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
    "board_invitations": "邀请制版块的成员邀请生命周期记录。",
    "tags": "主题标签及标签使用计数。",
    "topics": "论坛主题主表，保存主题状态、计数与排序信号。",
    "topic_tags": "主题与标签的多对多关联表。",
    "posts": "主题内帖子/楼层内容，保存原始 Markdown 与安全 HTML。",
    "post_revisions": "帖子编辑历史版本，保存编辑前正文、编辑人、原因和恢复来源。",
    "topic_reads": "用户对主题的阅读进度与主题通知级别。",
    "reactions": "用户对主题或帖子的点赞等表态记录。",
    "bookmarks": "用户收藏的主题或帖子。",
    "notifications": "通知中心消息及阅读状态。",
    "flags": "内容举报、处理状态与处理结果。",
    "audit_logs": "审核与管理操作审计日志。",
    "email_verification_codes": "邮箱注册验证码记录，用于账号激活和重发限流。",
    "uploads": "用户上传的头像、帖子图片和附件元数据及存储引用。",
    "user_security_tokens": "账号找回、邮箱变更等一次性安全令牌记录。",
    "user_sessions": "用户登录会话、刷新令牌哈希和设备撤销状态。",
    "user_recovery_codes": "TOTP 二次验证恢复码的哈希与使用状态。",
    "rate_limit_events": "写操作频控事件，用于用户/IP/邮箱等维度的滑动窗口计数。",
    "screened_rules": "邮箱、IP、URL 屏蔽名单规则及自动处置动作。",
    "spam_actions": "反垃圾系统自动拦截、禁言和频控处置记录。",
}

COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "users": {
        "username": "登录名和公开显示用户名，唯一。",
        "email": "账号邮箱，唯一。",
        "hashed_password": "哈希后的登录密码。",
        "avatar_url": "用户头像 URL。",
        "role": "用户角色：普通用户、版主或管理员。",
        "level": "用户等级，默认 0，用于成长体系和权限展示。",
        "status": "账号状态：正常、禁言、封禁或删除。",
        "last_seen_at": "用户最后活跃时间。",
        "two_factor_enabled": "是否启用 TOTP 二次验证。",
        "two_factor_secret": "TOTP Base32 密钥；为空表示未完成启用。",
    },
    "email_verification_codes": {
        "user_id": "待验证用户 ID。",
        "email": "接收验证码的邮箱地址。",
        "code_hash": "验证码的不可逆哈希值。",
        "sent_at": "验证码邮件发送时间。",
        "expires_at": "验证码失效时间。",
        "consumed_at": "验证码成功使用时间；为空表示未使用。",
        "attempt_count": "该验证码已被尝试校验的次数。",
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
    "board_invitations": {
        "board_id": "被邀请加入的版块 ID。",
        "inviter_id": "发出邀请的用户 ID。",
        "invitee_id": "被邀请的用户 ID。",
        "status": "邀请状态：pending、accepted、declined、revoked 或 expired。",
        "expires_at": "邀请过期时间；为空表示当前首版不自动过期。",
        "responded_at": "邀请被接受、拒绝或撤回的时间。",
        "revoked_by_id": "撤回邀请的用户 ID；为空表示未撤回。",
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
        "merged_into_topic_id": "主题合并后的目标主题 ID；为空表示未合并。",
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
    "post_revisions": {
        "post_id": "被编辑帖子 ID。",
        "topic_id": "被编辑帖子所属主题 ID，用于历史查询和审计关联。",
        "editor_id": "执行该次编辑或恢复操作的用户 ID；用户删除后为空。",
        "version_number": "同一帖子内递增的历史版本号，保存被覆盖前的内容版本。",
        "raw_md": "编辑前的原始 Markdown 内容。",
        "cooked_html": "编辑前已渲染/清洗的 HTML 内容。",
        "edit_reason": "编辑人填写的原因；为空表示未填写。",
        "summary": "系统生成或编辑人提供的版本摘要。",
        "restored_from_revision_id": "若该版本由恢复操作产生，指向被恢复的历史版本 ID；否则为空。",
        "created_at": "该历史版本保存时间（UTC）。",
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
    "uploads": {
        "user_id": "上传文件的用户 ID。",
        "board_id": "附件归属版块 ID；临时文件或头像为空。",
        "topic_id": "附件归属主题 ID；临时文件或头像为空。",
        "post_id": "附件归属帖子 ID；临时文件或头像为空。",
        "original_filename": "用户上传时的原始文件名，仅用于展示和下载名。",
        "storage_backend": "文件存储后端：local 或 s3。",
        "storage_key": "存储后端内的对象键，唯一且不含本地绝对路径。",
        "media_type": "服务端嗅探确认后的 MIME 类型。",
        "byte_size": "上传文件字节数。",
        "sha256": "文件内容 SHA-256 摘要，用于去重和审计。",
        "kind": "上传用途：post_attachment 或 avatar。",
        "status": "上传状态：temporary、attached、avatar 或 deleted。",
        "is_image": "是否为可内联展示的图片。",
        "expires_at": "临时上传过期时间；为空表示不自动过期。",
        "deleted_at": "上传软删除时间；为空表示仍可按权限读取。",
    },
    "user_security_tokens": {
        "user_id": "安全令牌所属用户 ID。",
        "purpose": "令牌用途：password_reset 或 email_change。",
        "token_hash": "一次性令牌的不可逆哈希值。",
        "email": "令牌发送目标邮箱；为空表示使用用户当前邮箱。",
        "payload": "令牌附带的 JSON 数据，如新邮箱地址。",
        "sent_at": "令牌发送时间。",
        "expires_at": "令牌失效时间。",
        "consumed_at": "令牌成功使用时间；为空表示未使用。",
        "attempt_count": "该令牌已被尝试校验的次数。",
    },
    "user_sessions": {
        "user_id": "会话所属用户 ID。",
        "refresh_token_hash": "刷新令牌的不可逆哈希值，用于撤销校验。",
        "user_agent": "登录设备/浏览器 User-Agent 摘要。",
        "ip_address": "登录请求来源 IP。",
        "last_seen_at": "该会话最后活跃时间。",
        "revoked_at": "会话撤销时间；为空表示仍有效。",
    },
    "user_recovery_codes": {
        "user_id": "恢复码所属用户 ID。",
        "code_hash": "恢复码的不可逆哈希值。",
        "used_at": "恢复码使用时间；为空表示仍可使用。",
    },
    "rate_limit_events": {
        "scope": "频控场景，如 register:ip 或 topic:user。",
        "identity_type": "频控主体类型：user、ip、email 或 account。",
        "identity_key": "频控主体归一化键。",
        "user_id": "触发频控事件的用户 ID；匿名路径为空。",
        "ip_address": "触发频控事件的请求来源 IP。",
        "created_at": "频控事件发生时间。",
    },
    "screened_rules": {
        "kind": "规则类型：email、ip 或 url。",
        "value": "管理员输入的原始屏蔽值。",
        "normalized_value": "用于匹配的归一化值。",
        "action": "命中后的处置动作：block 或 silence。",
        "note": "管理员备注；为空表示无备注。",
        "active": "规则是否启用。",
        "created_by_id": "创建规则的管理员 ID。",
    },
    "spam_actions": {
        "kind": "自动处置类型：rate_limit、screened_rule 或 new_user_screening。",
        "action": "自动处置动作：block 或 silence。",
        "reason": "触发处置的原因摘要。",
        "user_id": "被处置用户 ID；匿名注册/登录路径为空。",
        "ip_address": "触发处置的来源 IP。",
        "email": "命中的邮箱；非邮箱规则为空。",
        "url": "命中的 URL；非 URL 规则为空。",
        "screened_rule_id": "命中的屏蔽规则 ID；频控或新用户筛查为空。",
        "data": "处置上下文结构化数据，不包含密码或令牌。",
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
