from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import logging
import unicodedata
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import Settings
from app.core.exceptions import AppError, ValidationError
from app.core.permissions import is_admin
from app.db.base import utcnow
from app.models.catalog import CatalogCategory, CatalogProject, CatalogSubmission
from app.models.upload import Upload
from app.models.user import User
from app.schemas.catalog import (
    AdminCatalogSubmissionResponse,
    CatalogSubmissionCreateRequest,
    CatalogSubmissionCreateResponse,
)
from app.services.catalog import CatalogService
from app.services.uploads import UploadContent, UploadService

logger = logging.getLogger(__name__)
SUBMISSION_WINDOW = timedelta(hours=24)
MAX_SUBMISSIONS_PER_WINDOW = 3
MAX_REVIEW_LIST_SIZE = 100


class CatalogSubmissionError(Exception):
    """只暴露稳定的内部错误码；具体响应文案由 API 层决定。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CatalogSubmissionService:
    """保存匿名目录投稿，并由管理员审核后写入公开目录。"""

    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def create_submission(
        self,
        payload: CatalogSubmissionCreateRequest,
        request: Request,
        cover: UploadFile | None = None,
    ) -> CatalogSubmissionCreateResponse:
        """提交待审项目；同一 IP 在滚动 24 小时内最多成功投稿三次。"""

        digest = self._ip_digest(request)
        try:
            CatalogService._validate_destination("external", payload.url)
        except ValidationError as exc:
            raise CatalogSubmissionError("invalid") from exc
        url = self._canonical_url(payload.url)
        url_digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        upload_service = UploadService(self.session, self.settings)
        cover_upload: Upload | None = None
        committed = False

        try:
            if cover is not None:
                # 先做无锁预检并存储封面，避免在分类行锁期间等待对象存储网络。
                await self._check_quota_and_duplicate(digest, url, url_digest)
                cover_upload = await upload_service.create_submission_cover(cover)

            # 锁住迁移创建的首个分类，使并发投稿在计数与插入期间串行，空记录时也不会突破限额。
            guard = await self.session.scalar(
                select(CatalogCategory.id).order_by(CatalogCategory.id).limit(1).with_for_update()
            )
            if guard is None:
                raise CatalogSubmissionError("unavailable")
            # 锁内复核以抵御同一 IP 或同一链接的并发投稿。
            await self._check_quota_and_duplicate(digest, url, url_digest, locked=True)

            submission = CatalogSubmission(
                category_name=payload.category_name,
                project_name=payload.project_name,
                destination_url=url,
                author_name=payload.author_name,
                contact=payload.contact,
                submitter_ip_digest=digest,
                pending_url_digest=url_digest,
                cover_upload_id=cover_upload.id if cover_upload is not None else None,
                status="pending",
            )
            self.session.add(submission)
            await self.session.flush()
            result = CatalogSubmissionCreateResponse(id=submission.id, status="pending")
            await self.session.commit()
            committed = True
            return result
        except (CatalogSubmissionError, AppError):
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise CatalogSubmissionError("duplicate") from exc
        except SQLAlchemyError as exc:
            await self.session.rollback()
            # 数据库异常可能携带投稿参数；日志只记录异常类型，不写联系信息或链接。
            logger.error("catalog_submission_create_failed", extra={"error_type": type(exc).__name__})
            raise CatalogSubmissionError("unavailable") from exc
        except Exception:
            await self.session.rollback()
            raise
        finally:
            if cover_upload is not None and not committed:
                try:
                    await asyncio.to_thread(upload_service.delete_upload_files, cover_upload)
                except Exception as exc:
                    logger.error(
                        "catalog_submission_cover_cleanup_failed",
                        extra={"error_type": type(exc).__name__},
                    )

    async def _check_quota_and_duplicate(
        self, digest: str, url: str, url_digest: str, *, locked: bool = False
    ) -> None:
        """检查 IP 窗口和正式/待审链接；并发写入时须在分类行锁内复核。"""

        recent_query = (
            select(CatalogSubmission.id)
            .where(
                CatalogSubmission.submitter_ip_digest == digest,
                CatalogSubmission.created_at >= utcnow() - SUBMISSION_WINDOW,
            )
            .order_by(CatalogSubmission.created_at.desc(), CatalogSubmission.id.desc())
            .limit(MAX_SUBMISSIONS_PER_WINDOW)
        )
        if locked:
            # MySQL 可重复读的普通 SELECT 会沿用预检快照；锁定读才能看到先完成的投稿。
            recent_query = recent_query.with_for_update()
        recent_ids = (
            await self.session.scalars(
                recent_query
            )
        ).all()
        if len(recent_ids) >= MAX_SUBMISSIONS_PER_WINDOW:
            raise CatalogSubmissionError("rate_limited")
        if await self._project_with_url(url) or await self.session.scalar(
            select(CatalogSubmission.id)
            .where(CatalogSubmission.pending_url_digest == url_digest)
            .limit(1)
        ):
            raise CatalogSubmissionError("duplicate")

    async def list_pending(
        self, current_user: User, *, limit: int = MAX_REVIEW_LIST_SIZE
    ) -> list[AdminCatalogSubmissionResponse]:
        """仅管理员读取最多 100 条待审投稿，按提交时间和 ID 稳定排序。"""

        self._require_admin(current_user)
        if not 1 <= limit <= MAX_REVIEW_LIST_SIZE:
            raise CatalogSubmissionError("invalid")
        try:
            rows = (
                await self.session.scalars(
                    select(CatalogSubmission)
                    .where(CatalogSubmission.status == "pending")
                    .order_by(CatalogSubmission.created_at, CatalogSubmission.id)
                    .limit(limit)
                )
            ).all()
            return [self._response(row) for row in rows]
        except SQLAlchemyError as exc:
            await self.session.rollback()
            logger.error("catalog_submission_list_failed", extra={"error_type": type(exc).__name__})
            raise CatalogSubmissionError("unavailable") from exc

    async def review_submission(
        self, submission_id: str, decision: str, current_user: User
    ) -> AdminCatalogSubmissionResponse:
        """批准或拒绝一条投稿；批准时分类、项目与审核状态在同一事务提交。"""

        self._require_admin(current_user)
        if decision not in {"approve", "reject"}:
            raise CatalogSubmissionError("invalid")
        numeric_id = self._numeric_id(submission_id)

        # 同名分类并发创建可能触发唯一 slug 冲突；回滚后重新读取，复用先提交的分类。
        for attempt in range(2):
            try:
                submission = await self.session.scalar(
                    select(CatalogSubmission)
                    .where(CatalogSubmission.id == numeric_id)
                    .with_for_update()
                )
                if submission is None:
                    raise CatalogSubmissionError("not_found")
                target_status = "approved" if decision == "approve" else "rejected"
                if submission.status == target_status:
                    await self.session.commit()
                    return self._response(submission)
                if submission.status != "pending":
                    raise CatalogSubmissionError("conflict")

                if decision == "approve":
                    try:
                        CatalogService._validate_destination("external", submission.destination_url)
                    except ValidationError as exc:
                        raise CatalogSubmissionError("invalid") from exc
                    if await self._project_with_url(submission.destination_url):
                        raise CatalogSubmissionError("duplicate")
                    category = await self._visible_category(submission.category_name)
                    if category is None:
                        category = await self._new_category(submission.category_name)
                    cover_upload = await self._pending_cover(submission)
                    project = CatalogProject(
                        category_id=category.id,
                        slug=self._stable_slug("submission-project", submission.destination_url),
                        name=submission.project_name,
                        destination_url=submission.destination_url,
                        destination_kind="external",
                        author_name=submission.author_name,
                        icon_upload_id=cover_upload.id if cover_upload is not None else None,
                        sort_order=await self._next_project_sort_order(category.id),
                        is_visible=True,
                    )
                    self.session.add(project)
                    await self.session.flush()
                    submission.project_id = project.id
                    if cover_upload is not None:
                        # 审核通过后才转为正式目录图，读取仍受可见项目引用检查。
                        cover_upload.user_id = current_user.id
                        cover_upload.kind = "catalog_icon"
                        cover_upload.status = "catalog_icon"
                        cover_upload.expires_at = None
                elif submission.cover_upload_id is not None:
                    cover_upload = await self._pending_cover(submission)
                    if cover_upload is not None:
                        # 拒绝稿的封面恢复为临时状态，由既有后台任务删除对象文件。
                        cover_upload.status = "temporary"
                        cover_upload.expires_at = utcnow() - timedelta(seconds=1)

                # 联系方式只用于待审沟通；审核完成即清除，同时释放待审 URL 唯一键。
                submission.status = target_status
                submission.contact = None
                submission.pending_url_digest = None
                submission.reviewed_by_id = current_user.id
                submission.reviewed_at = utcnow()
                await self.session.flush()
                result = self._response(submission)
                await self.session.commit()
                return result
            except CatalogSubmissionError:
                await self.session.rollback()
                raise
            except IntegrityError as exc:
                await self.session.rollback()
                if attempt == 0 and decision == "approve":
                    continue
                logger.warning("catalog_submission_review_conflict", extra={"submission_id": numeric_id})
                raise CatalogSubmissionError("conflict") from exc
            except SQLAlchemyError as exc:
                await self.session.rollback()
                logger.error(
                    "catalog_submission_review_failed",
                    extra={"submission_id": numeric_id, "error_type": type(exc).__name__},
                )
                raise CatalogSubmissionError("unavailable") from exc
        raise CatalogSubmissionError("conflict")

    async def get_cover(
        self, submission_id: str, current_user: User
    ) -> UploadContent:
        """只允许管理员通过审核接口读取待审或已批准投稿的封面字节。"""

        self._require_admin(current_user)
        submission = await self.session.get(CatalogSubmission, self._numeric_id(submission_id))
        if submission is None or submission.status == "rejected" or submission.cover_upload_id is None:
            raise CatalogSubmissionError("not_found")
        upload = await self.session.get(Upload, submission.cover_upload_id)
        if (
            upload is None
            or upload.deleted_at is not None
            or upload.status not in {"catalog_submission_cover", "catalog_icon"}
            or not upload.is_image
        ):
            raise CatalogSubmissionError("not_found")
        return await UploadService(self.session, self.settings).read_upload_content(upload)

    async def _pending_cover(self, submission: CatalogSubmission) -> Upload | None:
        if submission.cover_upload_id is None:
            return None
        upload = await self.session.get(Upload, submission.cover_upload_id)
        if (
            upload is None
            or upload.kind != "catalog_submission_cover"
            or upload.status != "catalog_submission_cover"
            or upload.deleted_at is not None
            or not upload.is_image
        ):
            raise CatalogSubmissionError("invalid")
        return upload

    async def _visible_category(self, name: str) -> CatalogCategory | None:
        category = await self.session.scalar(
            select(CatalogCategory)
            .where(CatalogCategory.name == name, CatalogCategory.is_visible.is_(True))
            .order_by(CatalogCategory.id)
            .limit(1)
        )
        if category is not None:
            return category
        hidden = await self.session.scalar(
            select(CatalogCategory.id)
            .where(CatalogCategory.name == name, CatalogCategory.is_visible.is_(False))
            .limit(1)
        )
        if hidden is not None:
            # 同名分类已被管理员隐藏时禁止自动公开，需管理员先处理该分类。
            raise CatalogSubmissionError("hidden_category")
        return None

    async def _new_category(self, name: str) -> CatalogCategory:
        category = CatalogCategory(
            slug=self._stable_slug("submission-category", name),
            name=name,
            sort_order=int(
                await self.session.scalar(select(func.coalesce(func.max(CatalogCategory.sort_order), 0)))
            )
            + 1,
            is_visible=True,
        )
        self.session.add(category)
        await self.session.flush()
        return category

    async def _next_project_sort_order(self, category_id: str) -> int:
        return int(
            await self.session.scalar(
                select(func.coalesce(func.max(CatalogProject.sort_order), 0)).where(
                    CatalogProject.category_id == category_id
                )
            )
        ) + 1

    async def _project_with_url(self, url: str) -> bool:
        # 正式目录中的隐藏项目也算已收录，避免审核把它重新公开成重复项目。
        parsed = urlsplit(url)
        variants = {url}
        if parsed.path in {"", "/"}:
            alternate_path = "" if parsed.path == "/" else "/"
            variants.add(
                urlunsplit((parsed.scheme, parsed.netloc, alternate_path, parsed.query, parsed.fragment))
            )
        return (
            await self.session.scalar(
                select(CatalogProject.id)
                .where(CatalogProject.destination_url.in_(variants))
                .limit(1)
            )
        ) is not None

    def _ip_digest(self, request: Request) -> str:
        # 投稿与评分各自派生密钥；只信任 Nginx 覆盖的 X-Real-IP 或直连地址。
        root_secret = self.settings.jwt_secret_key
        if len(root_secret) < 32 or root_secret.startswith("change-me-"):
            raise CatalogSubmissionError("unavailable")
        raw_ip = request.headers.get("x-real-ip") or (
            request.client.host if request.client else ""
        )
        try:
            address = ipaddress.ip_address(raw_ip)
        except ValueError as exc:
            raise CatalogSubmissionError("unavailable") from exc
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            address = address.ipv4_mapped
        key = hmac.new(
            root_secret.encode("utf-8"), b"catalog-submission-ip-key-v1", hashlib.sha256
        ).digest()
        return hmac.new(key, address.compressed.encode("ascii"), hashlib.sha256).hexdigest()

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        authority = f"[{host}]" if ":" in host else host.lower()
        if parsed.port and parsed.port != 443:
            authority = f"{authority}:{parsed.port}"
        return urlunsplit(("https", authority, parsed.path or "/", parsed.query, parsed.fragment))

    @staticmethod
    def _stable_slug(prefix: str, value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
        return f"{prefix}-{digest}"

    @staticmethod
    def _numeric_id(value: str) -> str:
        if (
            len(value) > 19
            or not value.isascii()
            or not value.isdigit()
            or not 1 <= int(value) <= 2**63 - 1
        ):
            raise CatalogSubmissionError("not_found")
        return value

    @staticmethod
    def _require_admin(current_user: User) -> None:
        if not is_admin(current_user):
            raise CatalogSubmissionError("forbidden")

    @staticmethod
    def _response(submission: CatalogSubmission) -> AdminCatalogSubmissionResponse:
        return AdminCatalogSubmissionResponse(
            id=submission.id,
            category_name=submission.category_name,
            project_name=submission.project_name,
            url=submission.destination_url,
            author_name=submission.author_name,
            contact=submission.contact,
            cover_url=(
                f"/api/v1/admin/catalog/submissions/{submission.id}/cover"
                if submission.cover_upload_id is not None and submission.status != "rejected"
                else None
            ),
            status=submission.status,
            project_id=submission.project_id,
            reviewed_by_id=submission.reviewed_by_id,
            reviewed_at=submission.reviewed_at,
            created_at=submission.created_at,
            updated_at=submission.updated_at,
        )
