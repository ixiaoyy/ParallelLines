from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import PermissionDeniedError
from app.core.permissions import is_admin
from app.core.security import hash_password
from app.db.base import utcnow
from app.models.forum import Board, BoardMember, Post, Tag, Topic
from app.models.moderation import AuditLog
from app.models.user import User
from app.schemas.migrations import (
    MigrationBoardRecord,
    MigrationExportResponse,
    MigrationImportRequest,
    MigrationImportResponse,
    MigrationPostRecord,
    MigrationRowResult,
    MigrationTopicRecord,
    MigrationUserRecord,
)
from app.services.forum import calculate_hot_score, normalize_tag_name, render_markdown, slugify
from app.services.search import SearchIndexService

IMPORTED_PASSWORD_PLACEHOLDER = "imported-disabled-password"


class MigrationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def preview_import(
        self,
        payload: MigrationImportRequest,
        current_user: User,
    ) -> MigrationImportResponse:
        return await self._run_import(payload, current_user, dry_run=True)

    async def run_import(
        self,
        payload: MigrationImportRequest,
        current_user: User,
    ) -> MigrationImportResponse:
        return await self._run_import(payload, current_user, dry_run=False)

    async def export_site(self, current_user: User) -> MigrationExportResponse:
        self._require_admin(current_user)
        users = list(await self.session.scalars(select(User).order_by(User.created_at)))
        boards = list(await self.session.scalars(select(Board).order_by(Board.created_at)))
        topics = list(
            await self.session.scalars(
                select(Topic)
                .options(
                    selectinload(Topic.board), selectinload(Topic.author), selectinload(Topic.tags)
                )
                .where(Topic.deleted_at.is_(None), Topic.visibility == "public")
                .order_by(Topic.created_at)
            )
        )
        posts = list(
            await self.session.scalars(
                select(Post)
                .options(
                    selectinload(Post.topic).selectinload(Topic.board), selectinload(Post.author)
                )
                .where(Post.deleted_at.is_(None))
                .order_by(Post.created_at, Post.post_number)
            )
        )
        tags = list(await self.session.scalars(select(Tag).order_by(Tag.name)))
        return MigrationExportResponse(
            exported_at=utcnow(),
            users=[self._export_user(user) for user in users if user.status != "deleted"],
            boards=[self._export_board(board) for board in boards],
            topics=[self._export_topic(topic) for topic in topics],
            posts=[self._export_post(post) for post in posts if post.topic.visibility == "public"],
            tags=[self._export_tag(tag) for tag in tags],
        )

    async def _run_import(
        self,
        payload: MigrationImportRequest,
        current_user: User,
        *,
        dry_run: bool,
    ) -> MigrationImportResponse:
        self._require_admin(current_user)
        rows: list[MigrationRowResult] = []
        topic_external_map: dict[str, Topic] = {}
        created_topic_ids: list[str] = []

        users = await self._import_users(payload.users, rows)
        boards = await self._import_boards(payload.boards, rows, current_user)
        await self._refresh_existing_users(users, self._usernames_from_topics_posts(payload))
        await self._refresh_existing_boards(boards, {board.slug for board in payload.boards})
        await self._import_topics(
            payload.topics, rows, users, boards, topic_external_map, created_topic_ids
        )
        await self._import_posts(payload.posts, rows, users, boards, topic_external_map)

        for topic_id in created_topic_ids:
            await SearchIndexService(self.session).sync_topic(topic_id)

        self.session.add(
            AuditLog(
                actor_id=current_user.id,
                action="migration_import_preview" if dry_run else "migration_import_run",
                target_type="migration",
                target_id=current_user.id,
                board_id=None,
                data={
                    "source": payload.source,
                    "dry_run": dry_run,
                    "users": len(payload.users),
                    "boards": len(payload.boards),
                    "topics": len(payload.topics),
                    "posts": len(payload.posts),
                },
                created_at=utcnow(),
            )
        )

        if dry_run:
            await self.session.rollback()
        else:
            await self.session.commit()

        created = sum(1 for row in rows if row.action == "created")
        updated = sum(1 for row in rows if row.action == "updated")
        skipped = sum(1 for row in rows if row.action == "skipped")
        errors = sum(1 for row in rows if row.action == "error")
        return MigrationImportResponse(
            dry_run=dry_run,
            source=payload.source,
            created=created,
            updated=updated,
            skipped=skipped,
            errors=errors,
            rows=rows,
        )

    async def _import_users(
        self,
        records: list[MigrationUserRecord],
        rows: list[MigrationRowResult],
    ) -> dict[str, User]:
        imported: dict[str, User] = {}
        for index, record in enumerate(records):
            username = record.username.strip()
            email = str(record.email).strip().lower()
            existing = await self.session.scalar(
                select(User).where(or_(User.username == username, User.email == email))
            )
            if existing:
                imported[existing.username] = existing
                if record.is_persona and not existing.is_persona:
                    existing.is_persona = True
                    self._row(rows, "user", username, "updated", "已标记为马甲账号")
                    continue
                self._row(rows, "user", username, "skipped", "用户已存在")
                continue
            user = User(
                username=username,
                email=email,
                hashed_password=hash_password(IMPORTED_PASSWORD_PLACEHOLDER),
                display_name=record.display_name,
                role="user",
                status="active",
                locale="zh-CN",
                is_persona=record.is_persona,
            )
            self.session.add(user)
            await self.session.flush()
            imported[user.username] = user
            self._row(rows, "user", username, "created", f"导入用户 #{index + 1}")
        return imported

    async def _import_boards(
        self,
        records: list[MigrationBoardRecord],
        rows: list[MigrationRowResult],
        current_user: User,
    ) -> dict[str, Board]:
        imported: dict[str, Board] = {}
        for index, record in enumerate(records):
            slug = slugify(record.slug, fallback_prefix="board")[:96]
            existing = await self.session.scalar(select(Board).where(Board.slug == slug))
            if existing:
                imported[slug] = existing
                self._row(rows, "board", slug, "skipped", "版块已存在")
                continue
            board = Board(
                slug=slug,
                name=record.name.strip(),
                description=record.description.strip() or "Imported board",
                color=record.color,
                owner_id=current_user.id,
                visibility="public",
                topic_count=0,
                post_count=0,
                follower_count=1,
            )
            self.session.add(board)
            await self.session.flush()
            self.session.add(
                BoardMember(
                    board_id=board.id,
                    user_id=current_user.id,
                    role="owner",
                    notification_level="watching",
                )
            )
            imported[slug] = board
            self._row(rows, "board", slug, "created", f"导入版块 #{index + 1}")
        return imported

    async def _import_topics(
        self,
        records: list[MigrationTopicRecord],
        rows: list[MigrationRowResult],
        users: dict[str, User],
        boards: dict[str, Board],
        topic_external_map: dict[str, Topic],
        created_topic_ids: list[str],
    ) -> None:
        for index, record in enumerate(records):
            board = boards.get(record.board_slug)
            author = users.get(record.author_username)
            key = record.external_id or f"{record.board_slug}/{record.slug or record.title}"
            if board is None:
                self._row(rows, "topic", key, "error", "找不到目标版块")
                continue
            if author is None:
                self._row(rows, "topic", key, "error", "找不到主题作者")
                continue

            topic_slug = slugify(record.slug or record.title, fallback_prefix="topic")[:220]
            existing = await self.session.scalar(
                select(Topic)
                .options(selectinload(Topic.tags))
                .where(Topic.board_id == board.id, Topic.slug == topic_slug)
            )
            if existing:
                if record.external_id:
                    topic_external_map[record.external_id] = existing
                self._row(rows, "topic", key, "skipped", "主题已存在")
                continue

            normalized_tags = self._normalized_unique_tags(record.tags)
            tags = await self._resolve_tags(normalized_tags)
            created_at = record.created_at or utcnow()
            body = record.raw_md.strip() or record.title.strip()
            topic = Topic(
                board_id=board.id,
                user_id=author.id,
                title=record.title.strip(),
                slug=topic_slug,
                hot_score=calculate_hot_score(reply_count=0, like_count=0, view_count=0),
                last_posted_at=created_at,
                created_at=created_at,
                updated_at=created_at,
                tags=tags,
            )
            self.session.add(topic)
            await self.session.flush()
            post = Post(
                topic_id=topic.id,
                user_id=author.id,
                post_number=1,
                raw_md=body,
                cooked_html=render_markdown(body),
                created_at=created_at,
                updated_at=created_at,
            )
            self.session.add(post)
            for tag in tags:
                tag.topic_count += 1
            board.topic_count += 1
            board.post_count += 1
            await self.session.flush()
            if record.external_id:
                topic_external_map[record.external_id] = topic
            created_topic_ids.append(topic.id)
            self._row(rows, "topic", key, "created", f"导入主题 #{index + 1}")

    async def _import_posts(
        self,
        records: list[MigrationPostRecord],
        rows: list[MigrationRowResult],
        users: dict[str, User],
        boards: dict[str, Board],
        topic_external_map: dict[str, Topic],
    ) -> None:
        for index, record in enumerate(records):
            key = record.topic_external_id or record.topic_slug or f"post-{index + 1}"
            author = users.get(record.author_username)
            if author is None:
                self._row(rows, "post", key, "error", "找不到回复作者")
                continue
            topic = await self._resolve_post_topic(record, boards, topic_external_map)
            if topic is None:
                self._row(rows, "post", key, "error", "找不到目标主题")
                continue
            existing = await self.session.scalar(
                select(Post).where(
                    Post.topic_id == topic.id, Post.post_number == record.post_number
                )
            )
            if existing:
                self._row(rows, "post", key, "skipped", "帖子编号已存在")
                continue
            created_at = record.created_at or utcnow()
            post = Post(
                topic_id=topic.id,
                user_id=author.id,
                post_number=record.post_number,
                raw_md=record.raw_md.strip(),
                cooked_html=render_markdown(record.raw_md),
                created_at=created_at,
                updated_at=created_at,
            )
            self.session.add(post)
            topic.last_posted_at = max(topic.last_posted_at, created_at)
            topic.updated_at = utcnow()
            if record.post_number > 1:
                topic.reply_count += 1
                topic.hot_score = calculate_hot_score(
                    reply_count=topic.reply_count,
                    like_count=topic.like_count,
                    view_count=topic.view_count,
                )
            if topic.board:
                topic.board.post_count += 1
            await self.session.flush()
            await SearchIndexService(self.session).sync_topic(topic.id)
            self._row(rows, "post", key, "created", f"导入帖子 #{index + 1}")

    async def _resolve_post_topic(
        self,
        record: MigrationPostRecord,
        boards: dict[str, Board],
        topic_external_map: dict[str, Topic],
    ) -> Topic | None:
        if record.topic_external_id and record.topic_external_id in topic_external_map:
            return topic_external_map[record.topic_external_id]
        if not record.topic_slug:
            return None
        board = boards.get(record.board_slug)
        if board is None:
            return None
        return await self.session.scalar(
            select(Topic)
            .options(selectinload(Topic.board), selectinload(Topic.posts), selectinload(Topic.tags))
            .where(Topic.board_id == board.id, Topic.slug == record.topic_slug)
        )

    async def _refresh_existing_users(
        self,
        users: dict[str, User],
        usernames: set[str],
    ) -> None:
        missing = [username for username in usernames if username not in users]
        if not missing:
            return
        result = await self.session.scalars(select(User).where(User.username.in_(missing)))
        for user in result:
            users[user.username] = user

    async def _refresh_existing_boards(
        self,
        boards: dict[str, Board],
        slugs: set[str],
    ) -> None:
        missing = [slug for slug in slugs if slug not in boards]
        if not missing:
            return
        result = await self.session.scalars(select(Board).where(Board.slug.in_(missing)))
        for board in result:
            boards[board.slug] = board

    async def _resolve_tags(self, tag_names: Iterable[str]) -> list[Tag]:
        tags: list[Tag] = []
        for name in tag_names:
            tag = await self.session.scalar(select(Tag).where(Tag.name == name))
            if tag is None:
                tag = Tag(name=name, slug=slugify(name, fallback_prefix="tag")[:64], topic_count=0)
                self.session.add(tag)
                await self.session.flush()
            tags.append(tag)
        return tags

    def _usernames_from_topics_posts(self, payload: MigrationImportRequest) -> set[str]:
        names = {topic.author_username for topic in payload.topics}
        names.update(post.author_username for post in payload.posts)
        return names

    def _normalized_unique_tags(self, values: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            tag_name = normalize_tag_name(value)
            if tag_name and tag_name not in normalized:
                normalized.append(tag_name[:48])
        return normalized[:20]

    def _require_admin(self, current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError("admin_required", "Admin privileges required")

    def _row(
        self,
        rows: list[MigrationRowResult],
        resource: str,
        key: str,
        action: str,
        message: str,
    ) -> None:
        rows.append(MigrationRowResult(resource=resource, key=key, action=action, message=message))

    def _export_user(self, user: User) -> dict[str, object]:
        return {
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "status": user.status,
            "locale": user.locale,
            "is_persona": user.is_persona,
            "created_at": user.created_at,
        }

    def _export_board(self, board: Board) -> dict[str, object]:
        return {
            "slug": board.slug,
            "name": board.name,
            "description": board.description,
            "color": board.color,
            "visibility": board.visibility,
            "topic_count": board.topic_count,
            "post_count": board.post_count,
        }

    def _export_topic(self, topic: Topic) -> dict[str, object]:
        return {
            "board_slug": topic.board.slug,
            "slug": topic.slug,
            "title": topic.title,
            "author_username": topic.author.username,
            "tags": [tag.name for tag in topic.tags],
            "created_at": topic.created_at,
        }

    def _export_post(self, post: Post) -> dict[str, object]:
        return {
            "topic_slug": post.topic.slug,
            "board_slug": post.topic.board.slug,
            "author_username": post.author.username,
            "post_number": post.post_number,
            "raw_md": post.raw_md,
            "created_at": post.created_at,
        }

    def _export_tag(self, tag: Tag) -> dict[str, object]:
        return {"name": tag.name, "slug": tag.slug, "topic_count": tag.topic_count}
