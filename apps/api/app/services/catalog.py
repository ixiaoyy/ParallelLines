from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
from urllib.parse import urlsplit

from sqlalchemy import func, select
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
from app.models.catalog import CatalogCategory, CatalogProject, CatalogRating
from app.models.upload import Upload
from app.models.user import User
from app.schemas.catalog import (
    AdminCatalogCategoryResponse,
    AdminCatalogProjectResponse,
    AdminCatalogResponse,
    CatalogCategoryCreateRequest,
    CatalogCategoryResponse,
    CatalogCategoryUpdateRequest,
    CatalogProjectCreateRequest,
    CatalogProjectResponse,
    CatalogProjectUpdateRequest,
    CatalogRatingStateResponse,
    CatalogResponse,
)

logger = logging.getLogger(__name__)
INTERNAL_PROJECT_URL = "/play/generals-soldiers"
RATING_UNAVAILABLE_MESSAGE = "评分暂时不可用，请稍后重试。"
SAVE_FAILED_MESSAGE = "保存失败，请稍后重试。"


class CatalogService:
    """管理公开目录、管理员内容和访客的一次性评分。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

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
        return CatalogResponse(
            categories=[
                CatalogCategoryResponse(
                    id=category.id,
                    slug=category.slug,
                    name=category.name,
                    icon_url=self._icon_url(category.icon_upload_id),
                    projects=[
                        self._project_response(project, summaries, my_scores)
                        for project in self._sorted_projects(category.projects)
                        if project.is_visible
                    ],
                )
                for category in categories
            ]
        )

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
            summaries = await self._rating_summaries([resolved_project_id])
            average, count = summaries.get(resolved_project_id, (None, 0))
            return CatalogRatingStateResponse(
                project_id=resolved_project_id,
                average_score=average,
                rating_count=count,
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
        category = CatalogCategory(**payload.model_dump())
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
    ) -> dict[str, tuple[float | None, int]]:
        if not project_ids:
            return {}
        rows = (
            await self.session.execute(
                select(CatalogRating.project_id, func.avg(CatalogRating.score), func.count())
                .where(CatalogRating.project_id.in_(project_ids))
                .group_by(CatalogRating.project_id)
            )
        ).all()
        return {project_id: (float(average), int(count)) for project_id, average, count in rows}

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
        summaries: dict[str, tuple[float | None, int]],
        my_scores: dict[str, int],
    ) -> CatalogProjectResponse:
        average, count = summaries.get(project.id, (None, 0))
        return CatalogProjectResponse(
            id=project.id,
            slug=project.slug,
            name=project.name,
            url=project.destination_url,
            kind=project.destination_kind,
            description=project.description,
            icon_url=self._icon_url(project.icon_upload_id),
            created_at=project.created_at,
            average_score=average,
            rating_count=count,
            my_score=my_scores.get(project.id),
        )

    def _admin_project_response(
        self, project: CatalogProject, summaries: dict[str, tuple[float | None, int]]
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
        self, category: CatalogCategory, summaries: dict[str, tuple[float | None, int]]
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

        if len(self.settings.catalog_rating_ip_secret) < 32:
            if required:
                raise AppError(
                    "catalog_rating_unavailable", RATING_UNAVAILABLE_MESSAGE, status_code=503
                )
            return None
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
            self.settings.catalog_rating_ip_secret.encode("utf-8"),
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
        except IntegrityError as exc:
            await self.session.rollback()
            raise ValidationError() from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.exception("catalog_save_failed")
            raise AppError("catalog_save_failed", SAVE_FAILED_MESSAGE, status_code=503) from exc

    @staticmethod
    def _validate_destination(kind: str, url: str) -> None:
        # 外链仅允许 HTTPS；站内只开放将军战小兵的既有直达页。
        if kind == "internal":
            if url != INTERNAL_PROJECT_URL:
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
