from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import math
import re
from base64 import b64decode, urlsafe_b64encode
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from sqlalchemy import and_, case, func, literal, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.permissions import is_admin
from app.db.base import as_utc_datetime
from app.models.catalog import CatalogCategory, CatalogProject, CatalogRating
from app.models.upload import Upload
from app.models.user import User
from app.schemas.catalog import (
    SLUG_PATTERN,
    AdminCatalogCategoryResponse,
    AdminCatalogProjectResponse,
    AdminCatalogResponse,
    CatalogAiRatingResponse,
    CatalogCategoryCreateRequest,
    CatalogCategoryProjectsResponse,
    CatalogCategoryResponse,
    CatalogCategoryUpdateRequest,
    CatalogHeroResponse,
    CatalogOverviewCategoryResponse,
    CatalogOverviewResponse,
    CatalogProjectCreateRequest,
    CatalogProjectResponse,
    CatalogProjectUpdateRequest,
    CatalogPublicProjectResponse,
    CatalogRatingStateResponse,
    CatalogResponse,
    CatalogViewStateResponse,
)
from app.services.catalog_ai_ratings import CatalogAiRatingService
from app.services.catalog_cache import invalidate_public_catalog_cache

logger = logging.getLogger(__name__)
# 只允许已交付的游戏直达页，后台编辑与隐藏条目也使用同一白名单。
INTERNAL_PROJECT_URLS = frozenset(
    {
        "/play/generals-soldiers",
        "/play/snake-escape",
        "/play/flappy-dunk",
        "/games/illusion-prototype/index.html",
    }
)
RATING_UNAVAILABLE_MESSAGE = "评分暂时不可用，请稍后重试。"
SAVE_FAILED_MESSAGE = "保存失败，请稍后重试。"
HERO_BATCH_SIZE = 6
MAX_CATALOG_SLUGS = 64


def parse_catalog_slug_list(raw: str | None) -> tuple[str, ...] | None:
    """解析有界 slug 参数；缺失保持 None，显式空串返回空候选，重复项保留首次顺序。"""

    if raw is None:
        return None
    if not raw.strip():
        return ()
    values = [value.strip() for value in raw.split(",")]
    if len(values) > MAX_CATALOG_SLUGS or any(
        len(value) > 80 or re.fullmatch(SLUG_PATTERN, value) is None for value in values
    ):
        raise ValidationError("invalid_catalog_slugs", "Catalog slug list is invalid")
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True)
class CatalogPublicLink:
    """公开首屏所需链接资料，不包含评分、访客身份或打开统计。"""

    url: str
    name: str
    description: str | None


class CatalogService:
    """管理公开目录、管理员内容和访客的一次性评分。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def public_project_links(self) -> list[CatalogPublicLink]:
        """一次读取 SEO 所需公开链接，沿用分类及项目顺序；不聚合评分、不写计数。"""

        # HTML 仅使用链接资料；在数据库同时过滤父分类和项目，避免加载隐藏记录或评分。
        rows = (
            await self.session.execute(
                select(
                    CatalogProject.destination_url,
                    CatalogProject.name,
                    CatalogProject.description,
                )
                .join(CatalogCategory, CatalogCategory.id == CatalogProject.category_id)
                .where(CatalogCategory.is_visible.is_(True), CatalogProject.is_visible.is_(True))
                .order_by(
                    CatalogCategory.sort_order, CatalogCategory.id,
                    CatalogProject.sort_order, CatalogProject.id,
                )
            )
        ).all()
        return [
            CatalogPublicLink(url=url, name=name, description=description)
            for url, name, description in rows
        ]

    async def public_catalog(self, request: Request | None = None) -> CatalogResponse:
        """返回可见目录；有请求时按访客 IP 附上首次评分。"""

        categories = await self._load_categories(visible_only=True)
        projects = [
            project
            for category in categories
            for project in category.projects
            if project.is_visible
        ]
        summaries = await self._rating_summaries([project.id for project in projects])
        digest = self._ip_digest(request, required=False) if request is not None else None
        my_scores = await self._my_scores([project.id for project in projects], digest)
        ai_summaries = await CatalogAiRatingService(self.session).public_summaries(
            [project.id for project in projects]
        )
        return CatalogResponse(
            categories=[
                CatalogCategoryResponse(
                    id=category.id,
                    slug=category.slug,
                    name=category.name,
                    icon_url=self._icon_url(category.icon_upload_id),
                    projects=[
                        self._project_response(project, summaries, my_scores, ai_summaries)
                        for project in self._sorted_projects(category.projects)
                        if project.is_visible
                    ],
                )
                for category in categories
            ]
        )

    async def public_overview(
        self, *, hero_slugs: tuple[str, ...] | None = None, hero_offset: int = 0,
    ) -> CatalogOverviewResponse:
        """返回分类计数和六张公开推荐；候选仅来自前端名单，不读取访客评分。"""

        # 列投影避开 CatalogCategory.projects 的 selectin 全集加载。
        counts = select(
            CatalogProject.category_id, func.count().label("total"),
        ).where(CatalogProject.is_visible.is_(True)).group_by(
            CatalogProject.category_id,
        ).subquery()
        category_rows = (await self.session.execute(select(
            CatalogCategory.id, CatalogCategory.slug, CatalogCategory.name,
            CatalogCategory.icon_upload_id, func.coalesce(counts.c.total, 0).label("total"),
        ).outerjoin(counts, counts.c.category_id == CatalogCategory.id).where(
            CatalogCategory.is_visible.is_(True),
        ).order_by(CatalogCategory.sort_order, CatalogCategory.id))).all()
        categories = [CatalogOverviewCategoryResponse(
            id=row.id, slug=row.slug, name=row.name,
            icon_url=self._icon_url(row.icon_upload_id), total=row.total,
        ) for row in category_rows]
        if hero_slugs == ():
            return CatalogOverviewResponse(
                categories=categories,
                hero=CatalogHeroResponse(projects=[], total=0, next_offset=None),
            )

        # 先读轻量候选标识和 AI 分；仅选中的六张才读取完整项目及人工评分聚合。
        query = select(
            CatalogProject.id, CatalogCategory.slug.label("category_slug"),
        ).join(CatalogCategory, CatalogCategory.id == CatalogProject.category_id).where(
            CatalogCategory.is_visible.is_(True), CatalogProject.is_visible.is_(True),
        ).order_by(
            CatalogCategory.sort_order, CatalogCategory.id,
            CatalogProject.sort_order, CatalogProject.id,
        )
        if hero_slugs is not None:
            query = query.where(CatalogProject.slug.in_(hero_slugs))
        rows = (await self.session.execute(query)).all()
        ai_summaries = await CatalogAiRatingService(self.session).public_summaries(
            [row.id for row in rows],
        )

        def recommendation_key(row):
            """有效 AI 分降序；未知分在后，同分保持输入的原 API 顺序。"""
            summary = ai_summaries.get(row.id)
            score = summary.score if summary is not None else None
            valid = score is not None and math.isfinite(score) and 0 <= score <= 10
            return (not valid, -score if valid else 0)

        ranked = sorted(rows, key=recommendation_key)
        selected = ranked[hero_offset:hero_offset + HERO_BATCH_SIZE]
        selected_ids = [row.id for row in selected]
        projects = (await self.session.scalars(select(CatalogProject).join(
            CatalogCategory, CatalogCategory.id == CatalogProject.category_id,
        ).where(
            CatalogProject.id.in_(selected_ids), CatalogProject.is_visible.is_(True),
            CatalogCategory.is_visible.is_(True),
        ).limit(HERO_BATCH_SIZE))).all() if selected_ids else []
        by_id = {project.id: project for project in projects}
        summaries = await self._rating_summaries(selected_ids)
        next_offset = hero_offset + len(selected)
        return CatalogOverviewResponse(categories=categories, hero=CatalogHeroResponse(
            projects=[self._public_project_response(
                by_id[row.id], row.category_slug, summaries, ai_summaries,
            ) for row in selected if row.id in by_id],
            total=len(ranked), next_offset=next_offset if next_offset < len(ranked) else None,
        ))

    async def public_category_projects(
        self, slug: str, *, limit: int, cursor: str | None = None,
        priority_slugs: tuple[str, ...] = (),
    ) -> CatalogCategoryProjectsResponse:
        """SQL 游标读取一类公开项目；limit 1..60，游标绑定分类和同秒优先顺序。"""

        if not 1 <= limit <= 60:
            raise ValidationError("invalid_limit", "Catalog page limit is invalid")
        category = (await self.session.execute(select(
            CatalogCategory.id, CatalogCategory.slug,
        ).where(CatalogCategory.slug == slug, CatalogCategory.is_visible.is_(True)))).one_or_none()
        if category is None:
            raise NotFoundError()
        priorities = {value: index for index, value in enumerate(priority_slugs)}
        rank = case(priorities, value=CatalogProject.slug, else_=len(priorities)) \
            if priorities else literal(0)
        scope = hashlib.sha256(json.dumps(
            [category.id, category.slug, priority_slugs], separators=(",", ":"),
        ).encode()).hexdigest()
        position = self._category_cursor(cursor, scope, len(priorities))
        conditions = [
            CatalogProject.category_id == category.id, CatalogProject.is_visible.is_(True),
        ]
        total = await self.session.scalar(select(func.count()).select_from(CatalogProject).where(
            *conditions,
        ))
        query = select(CatalogProject).join(
            CatalogCategory, CatalogCategory.id == CatalogProject.category_id,
        ).where(*conditions, CatalogCategory.is_visible.is_(True))
        if position is not None:
            timestamp, priority, project_id = position
            # 与 created_at DESC、优先序 ASC、数值 ID DESC 完全对应，跨批不漏重。
            query = query.where(or_(
                CatalogProject.created_at < timestamp,
                and_(CatalogProject.created_at == timestamp, rank > priority),
                and_(CatalogProject.created_at == timestamp, rank == priority,
                     CatalogProject.id < project_id),
            ))
        # MySQL 将 ORDER BY 绑定常量视作列序号；没有优先名单时完全省略该排序项。
        projects = (await self.session.scalars(query.order_by(
            CatalogProject.created_at.desc(), *([rank] if priorities else []),
            CatalogProject.id.desc(),
        ).limit(limit + 1))).all()
        has_more = len(projects) > limit
        projects = projects[:limit]
        project_ids = [project.id for project in projects]
        summaries = await self._rating_summaries(project_ids)
        ai_summaries = await CatalogAiRatingService(self.session).public_summaries(project_ids)
        next_cursor = None
        if has_more:
            last = projects[-1]
            payload = [1, scope, as_utc_datetime(last.created_at).isoformat(),
                       priorities.get(last.slug, len(priorities)), last.id]
            next_cursor = urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()) \
                .decode().rstrip("=")
        return CatalogCategoryProjectsResponse(
            category_id=category.id, category_slug=category.slug,
            projects=[self._public_project_response(
                project, category.slug, summaries, ai_summaries,
            ) for project in projects], total=total or 0,
            next_cursor=next_cursor, has_more=has_more,
        )

    @staticmethod
    def _category_cursor(
        raw: str | None, scope: str, max_priority: int,
    ) -> tuple[datetime, int, str] | None:
        """校验不透明位置游标；格式、版本、分类或排序不匹配均报 422，不回退首批。"""

        if raw is None:
            return None
        try:
            if not raw or len(raw) > 2048:
                raise ValueError("cursor length")
            decoded = b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)
            value = json.loads(decoded)
            if not isinstance(value, list) or len(value) != 5:
                raise ValueError("cursor shape")
            version, binding, timestamp, priority, project_id = value
            if type(version) is not int or version != 1 or binding != scope:
                raise ValueError("cursor scope")
            if type(priority) is not int or not 0 <= priority <= max_priority:
                raise ValueError("cursor priority")
            if (not isinstance(project_id, str) or len(project_id) > 19
                    or not project_id.isascii() or not project_id.isdigit()
                    or not 1 <= int(project_id) <= 2**63 - 1):
                raise ValueError("cursor id")
            # 数据库存 UTC DATETIME；API 的时区字符串不能直接作为数据库比较基准。
            parsed = as_utc_datetime(datetime.fromisoformat(timestamp)).replace(tzinfo=None)
            return parsed, priority, project_id
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValidationError("invalid_cursor", "Pagination cursor is invalid") from exc

    def _public_project_response(
        self, project: CatalogProject, category_slug: str,
        summaries: dict[str, tuple[float | None, int, int]],
        ai_summaries: dict[str, CatalogAiRatingResponse],
    ) -> CatalogPublicProjectResponse:
        """从现有卡片投影生成公开 DTO；传空个人评分集合，固定 my_score=null。"""

        return CatalogPublicProjectResponse(
            **self._project_response(project, summaries, {}, ai_summaries).model_dump(),
            category_slug=category_slug,
        )

    async def record_view(self, project_id: str) -> CatalogViewStateResponse:
        """为指定公开项目累计一次打开并返回总数；不可见项目不写入且返回 404。"""

        resolved_project_id = self._numeric_id(project_id)
        try:
            # 项目与父分类均可见时才原子递增，避免旧 ORM 对象或并发请求覆盖计数。
            result = await self.session.execute(
                update(CatalogProject)
                .where(
                    CatalogProject.id == resolved_project_id,
                    CatalogProject.is_visible.is_(True),
                    CatalogProject.category_id.in_(
                        select(CatalogCategory.id).where(CatalogCategory.is_visible.is_(True))
                    ),
                )
                .values(
                    view_count=CatalogProject.view_count + 1,
                    # 浏览统计不改变管理员的内容编辑时间。
                    updated_at=CatalogProject.updated_at,
                )
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                # 隐藏或不存在的项目保持统一 404，并结束本次无效写事务。
                await self.session.rollback()
                raise NotFoundError()
            view_count = await self.session.scalar(
                select(CatalogProject.view_count).where(CatalogProject.id == resolved_project_id)
            )
            await self.session.commit()
            # 公开缓存含浏览统计，真实提交成功后再失效，不回退已返回的服务端计数。
            invalidate_public_catalog_cache()
            return CatalogViewStateResponse(project_id=resolved_project_id, view_count=view_count)
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.exception("catalog_view_failed", extra={"project_id": project_id})
            raise AppError(
                "catalog_view_unavailable", SAVE_FAILED_MESSAGE, status_code=503
            ) from exc

    async def rate_project(
        self, project_id: str, score: int, request: Request
    ) -> CatalogRatingStateResponse:
        """同一 IP 对同一可见项目只保留第一次评分，并处理并发重复提交。"""

        digest = self._ip_digest(request, required=True)
        try:
            project = await self.session.scalar(
                select(CatalogProject)
                .join(CatalogCategory, CatalogProject.category_id == CatalogCategory.id)
                .where(
                    CatalogProject.id == self._numeric_id(project_id),
                    CatalogProject.is_visible.is_(True),
                    CatalogCategory.is_visible.is_(True),
                )
            )
            if project is None:
                raise NotFoundError()
            resolved_project_id = project.id

            # 先查既有评分；唯一约束负责挡住两个同时到达的首次请求。
            rating = await self.session.scalar(
                select(CatalogRating).where(
                    CatalogRating.project_id == project.id,
                    CatalogRating.ip_digest == digest,
                )
            )
            if rating is None:
                try:
                    async with self.session.begin_nested():
                        rating = CatalogRating(project_id=project.id, ip_digest=digest, score=score)
                        self.session.add(rating)
                        await self.session.flush()
                except IntegrityError:
                    # 唯一键冲突后开启新事务，避开 MySQL 旧快照并读取原票。
                    await self.session.rollback()
                    rating = await self.session.scalar(
                        select(CatalogRating).where(
                            CatalogRating.project_id == resolved_project_id,
                            CatalogRating.ip_digest == digest,
                        )
                    )
                    if rating is None:
                        raise
            await self.session.commit()
            # 人工评分会改变公开聚合值；个人票仍只通过私有接口返回。
            invalidate_public_catalog_cache()
            summaries = await self._rating_summaries([resolved_project_id])
            average, count, score_sum = summaries.get(resolved_project_id, (None, 0, 0))
            return CatalogRatingStateResponse(
                project_id=resolved_project_id,
                average_score=average,
                rating_count=count,
                rating_score_sum=score_sum,
                my_score=rating.score,
            )
        except NotFoundError:
            raise
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.exception("catalog_rating_failed", extra={"project_id": project_id})
            raise AppError(
                "catalog_rating_unavailable", RATING_UNAVAILABLE_MESSAGE, status_code=503
            ) from exc

    async def admin_catalog(self, current_user: User) -> AdminCatalogResponse:
        """返回全部分类和项目供管理员编辑，隐藏项目也保留在列表。"""

        self._require_admin(current_user)
        categories = await self._load_categories(visible_only=False)
        project_ids = [project.id for category in categories for project in category.projects]
        summaries = await self._rating_summaries(project_ids)
        return AdminCatalogResponse(
            categories=[
                self._admin_category_response(category, summaries) for category in categories
            ]
        )

    async def create_category(
        self, payload: CatalogCategoryCreateRequest, current_user: User
    ) -> AdminCatalogCategoryResponse:
        """新增分类，并在同一事务内绑定已上传的管理员图标。"""

        self._require_admin(current_user)
        self._require_nonempty(payload.name)
        await self._check_category_slug(payload.slug)
        upload = await self._validate_icon(payload.icon_upload_id, current_user)
        # 新对象的空集合先在内存中初始化，提交后响应不触发异步懒加载。
        category = CatalogCategory(**payload.model_dump(), projects=[])
        self.session.add(category)
        self._bind_icon(upload)
        await self._commit_admin()
        return self._admin_category_response(category, {})

    async def update_category(
        self, category_id: str, payload: CatalogCategoryUpdateRequest, current_user: User
    ) -> AdminCatalogCategoryResponse:
        """局部更新分类；隐藏操作保留项目和历史评分。"""

        self._require_admin(current_user)
        category = await self._get_category(category_id)
        changes = payload.model_dump(exclude_unset=True)
        self._require_nonnull(changes, {"slug", "name", "sort_order", "is_visible"})
        if "name" in changes:
            self._require_nonempty(changes["name"])
        if "slug" in changes:
            await self._check_category_slug(changes["slug"], exclude_id=category.id)
        upload = (
            await self._validate_icon(changes["icon_upload_id"], current_user)
            if "icon_upload_id" in changes
            else None
        )
        for key, value in changes.items():
            setattr(category, key, value)
        self._bind_icon(upload)
        await self._commit_admin()
        summaries = await self._rating_summaries([project.id for project in category.projects])
        return self._admin_category_response(category, summaries)

    async def create_project(
        self, payload: CatalogProjectCreateRequest, current_user: User
    ) -> AdminCatalogProjectResponse:
        """新增 HTTPS 外链或获准的站内游戏入口。"""

        self._require_admin(current_user)
        self._require_nonempty(payload.name)
        self._validate_destination(payload.kind, payload.url)
        await self._get_category(payload.category_id)
        await self._check_project_slug(payload.slug)
        upload = await self._validate_icon(payload.icon_upload_id, current_user)
        values = payload.model_dump(exclude={"url", "kind"})
        project = CatalogProject(
            **values, destination_url=payload.url, destination_kind=payload.kind
        )
        self.session.add(project)
        self._bind_icon(upload)
        await self._commit_admin()
        return self._admin_project_response(project, {})

    async def update_project(
        self, project_id: str, payload: CatalogProjectUpdateRequest, current_user: User
    ) -> AdminCatalogProjectResponse:
        """局部更新项目；原有评分继续归属同一项目 ID。"""

        self._require_admin(current_user)
        project = await self._get_project(project_id)
        changes = payload.model_dump(exclude_unset=True)
        self._require_nonnull(
            changes,
            {"category_id", "slug", "name", "url", "kind", "sort_order", "is_visible"},
        )
        if "name" in changes:
            self._require_nonempty(changes["name"])
        if "category_id" in changes:
            await self._get_category(changes["category_id"])
        if "slug" in changes:
            await self._check_project_slug(changes["slug"], exclude_id=project.id)
        self._validate_destination(
            changes.get("kind", project.destination_kind),
            changes.get("url", project.destination_url),
        )
        upload = (
            await self._validate_icon(changes["icon_upload_id"], current_user)
            if "icon_upload_id" in changes
            else None
        )
        for key, value in changes.items():
            if key == "url":
                project.destination_url = value
            elif key == "kind":
                project.destination_kind = value
            else:
                setattr(project, key, value)
        self._bind_icon(upload)
        await self._commit_admin()
        summaries = await self._rating_summaries([project.id])
        return self._admin_project_response(project, summaries)

    async def _load_categories(self, *, visible_only: bool) -> list[CatalogCategory]:
        query = select(CatalogCategory).options(selectinload(CatalogCategory.projects))
        if visible_only:
            query = query.where(CatalogCategory.is_visible.is_(True))
        categories = (await self.session.scalars(query)).all()
        return sorted(categories, key=lambda category: (category.sort_order, int(category.id)))

    async def _rating_summaries(
        self, project_ids: list[str]
    ) -> dict[str, tuple[float | None, int, int]]:
        if not project_ids:
            return {}
        rows = (
            await self.session.execute(
                # 作者排行累计每张评分的原始分值，与平均分和评分人数同次聚合。
                select(
                    CatalogRating.project_id,
                    func.avg(CatalogRating.score),
                    func.count(),
                    func.sum(CatalogRating.score),
                )
                .where(CatalogRating.project_id.in_(project_ids))
                .group_by(CatalogRating.project_id)
            )
        ).all()
        return {
            project_id: (float(average), int(count), int(score_sum))
            for project_id, average, count, score_sum in rows
        }

    async def _my_scores(self, project_ids: list[str], digest: str | None) -> dict[str, int]:
        if not project_ids or digest is None:
            return {}
        rows = (
            await self.session.execute(
                select(CatalogRating.project_id, CatalogRating.score).where(
                    CatalogRating.project_id.in_(project_ids),
                    CatalogRating.ip_digest == digest,
                )
            )
        ).all()
        return {project_id: score for project_id, score in rows}

    def _project_response(
        self,
        project: CatalogProject,
        summaries: dict[str, tuple[float | None, int, int]],
        my_scores: dict[str, int],
        ai_summaries: dict[str, CatalogAiRatingResponse] | None = None,
    ) -> CatalogProjectResponse:
        average, count, score_sum = summaries.get(project.id, (None, 0, 0))
        return CatalogProjectResponse(
            id=project.id,
            slug=project.slug,
            name=project.name,
            url=project.destination_url,
            kind=project.destination_kind,
            description=project.description,
            author_name=project.author_name,
            author_url=project.author_url,
            icon_url=self._icon_url(project.icon_upload_id),
            created_at=project.created_at,
            view_count=project.view_count,
            ai_rating=ai_summaries.get(project.id) if ai_summaries else None,
            average_score=average,
            rating_count=count,
            rating_score_sum=score_sum,
            my_score=my_scores.get(project.id),
        )

    def _admin_project_response(
        self, project: CatalogProject, summaries: dict[str, tuple[float | None, int, int]]
    ) -> AdminCatalogProjectResponse:
        public = self._project_response(project, summaries, {})
        return AdminCatalogProjectResponse(
            **public.model_dump(),
            category_id=project.category_id,
            icon_upload_id=project.icon_upload_id,
            sort_order=project.sort_order,
            is_visible=project.is_visible,
            updated_at=project.updated_at,
        )

    def _admin_category_response(
        self, category: CatalogCategory, summaries: dict[str, tuple[float | None, int, int]]
    ) -> AdminCatalogCategoryResponse:
        return AdminCatalogCategoryResponse(
            id=category.id,
            slug=category.slug,
            name=category.name,
            icon_upload_id=category.icon_upload_id,
            icon_url=self._icon_url(category.icon_upload_id),
            sort_order=category.sort_order,
            is_visible=category.is_visible,
            created_at=category.created_at,
            updated_at=category.updated_at,
            projects=[
                self._admin_project_response(project, summaries)
                for project in self._sorted_projects(category.projects)
            ],
        )

    @staticmethod
    def _sorted_projects(projects: list[CatalogProject]) -> list[CatalogProject]:
        return sorted(projects, key=lambda project: (project.sort_order, int(project.id)))

    @staticmethod
    def _icon_url(upload_id: str | None) -> str | None:
        return f"/uploads/{upload_id}/content" if upload_id is not None else None

    def _ip_digest(self, request: Request, *, required: bool) -> str | None:
        """只使用 Nginx 覆盖的 X-Real-IP 或直连地址，不保存原始 IP。"""

        # 已有专用密钥保留原始字节，包括首尾空白，避免改变历史评分的访客身份。
        configured_secret = self.settings.catalog_rating_ip_secret
        if configured_secret and len(configured_secret) < 32:
            if required:
                raise AppError(
                    "catalog_rating_unavailable", RATING_UNAVAILABLE_MESSAGE, status_code=503
                )
            return None
        # 没有单独配置时从现有生产 JWT 密钥派生用途隔离的评分密钥，避免新站上线后评分恒为 503。
        if configured_secret:
            digest_key = configured_secret.encode("utf-8")
        else:
            root_secret = self.settings.jwt_secret_key
            if len(root_secret) < 32 or root_secret.startswith("change-me-"):
                if required:
                    raise AppError(
                        "catalog_rating_unavailable", RATING_UNAVAILABLE_MESSAGE, status_code=503
                    )
                return None
            # 十六进制子密钥可原样固定到专用配置，便于轮换 JWT 时保留评分身份。
            digest_key = hmac.new(
                root_secret.encode("utf-8"), b"catalog-rating-ip-key-v1", hashlib.sha256
            ).hexdigest().encode("ascii")
        raw_ip = request.headers.get("x-real-ip") or (request.client.host if request.client else "")
        try:
            address = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            if required:
                raise AppError(
                    "catalog_rating_unavailable", RATING_UNAVAILABLE_MESSAGE, status_code=503
                ) from exc
            return None
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        return hmac.new(
            digest_key,
            address.compressed.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

    async def _get_category(self, category_id: str) -> CatalogCategory:
        category = await self.session.get(CatalogCategory, self._numeric_id(category_id))
        if category is None:
            raise NotFoundError()
        return category

    async def _get_project(self, project_id: str) -> CatalogProject:
        project = await self.session.get(CatalogProject, self._numeric_id(project_id))
        if project is None:
            raise NotFoundError()
        return project

    async def _validate_icon(self, upload_id: str | None, current_user: User) -> Upload | None:
        if upload_id is None:
            return None
        upload = await self.session.get(Upload, self._numeric_id(upload_id))
        if (
            upload is None
            or upload.user_id != current_user.id
            or upload.kind != "catalog_icon"
            or upload.status not in {"temporary", "catalog_icon"}
            or upload.deleted_at is not None
            or not upload.is_image
        ):
            raise ValidationError()
        return upload

    @staticmethod
    def _bind_icon(upload: Upload | None) -> None:
        if upload is not None:
            # 绑定后停止临时文件清理，公开读取仍受可见目录引用约束。
            upload.status = "catalog_icon"
            upload.expires_at = None

    async def _check_category_slug(self, slug: str, *, exclude_id: str | None = None) -> None:
        query = select(CatalogCategory.id).where(CatalogCategory.slug == slug)
        if exclude_id is not None:
            query = query.where(CatalogCategory.id != exclude_id)
        if await self.session.scalar(query) is not None:
            raise ValidationError()

    async def _check_project_slug(self, slug: str, *, exclude_id: str | None = None) -> None:
        query = select(CatalogProject.id).where(CatalogProject.slug == slug)
        if exclude_id is not None:
            query = query.where(CatalogProject.id != exclude_id)
        if await self.session.scalar(query) is not None:
            raise ValidationError()

    async def _commit_admin(self) -> None:
        try:
            await self.session.commit()
            # 新增、编辑和隐藏都改变公开目录，失败事务不得清理成功快照。
            invalidate_public_catalog_cache()
        except IntegrityError as exc:
            await self.session.rollback()
            raise ValidationError() from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.exception("catalog_save_failed")
            raise AppError("catalog_save_failed", SAVE_FAILED_MESSAGE, status_code=503) from exc

    @staticmethod
    def _validate_destination(kind: str, url: str) -> None:
        # 外链仅允许 HTTPS；站内仅开放白名单登记的精确游戏地址。
        if kind == "internal":
            if url not in INTERNAL_PROJECT_URLS:
                raise ValidationError()
            return
        if kind != "external" or any(char.isspace() or ord(char) < 32 for char in url):
            raise ValidationError()
        if "\\" in url:
            raise ValidationError()
        try:
            parsed = urlsplit(url)
            host = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ValidationError() from exc
        if (
            parsed.scheme != "https"
            or not host
            or parsed.username
            or parsed.password
            or port == 0
        ):
            raise ValidationError()

    @staticmethod
    def _numeric_id(value: str) -> str:
        if (
            len(value) > 19
            or not value.isascii()
            or not value.isdigit()
            or not 1 <= int(value) <= 2**63 - 1
        ):
            raise NotFoundError()
        return value

    @staticmethod
    def _require_nonempty(value: str) -> None:
        if not value:
            raise ValidationError()

    @staticmethod
    def _require_nonnull(changes: dict[str, object], required_names: set[str]) -> None:
        if any(changes.get(name) is None for name in required_names if name in changes):
            raise ValidationError()

    @staticmethod
    def _require_admin(current_user: User) -> None:
        if not is_admin(current_user):
            raise PermissionDeniedError()
