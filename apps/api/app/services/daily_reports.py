from __future__ import annotations

import json
import re

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationError
from app.models.daily_report import (
    DailyReport,
    DailyReportMessage,
    DailyReportProfile,
    DailyReportPromptVersion,
    DailyReportSession,
)
from app.models.user import User
from app.schemas.daily_report import (
    DailyReportInput,
    DailyReportPreferenceAcceptRequest,
    DailyReportProfileResponse,
    DailyReportProfileUpdateRequest,
    DailyReportResponse,
    DailyReportSessionConfirmRequest,
    DailyReportSessionFollowupRequest,
    DailyReportSessionResponse,
    DailyReportSessionStartRequest,
)
from app.services.daily_report_provider import (
    DailyReportProviderResult,
    LocalDailyReportProvider,
    configured_provider,
)

DEFAULT_USER_PROMPT = (
    "语气专业、自然、克制；优先呈现真实工作的推进过程、检查动作和实际影响；"
    "避免空泛口号、夸张成绩和连续多天完全相同的开头。"
)
SYSTEM_PROMPT = """你是 ParallelLines 的个人日报助手。必须遵守：
1. 只能改写用户明确提供的真实工作，不得新增项目、会议、客户、协作对象、数量、完成状态或交付物。
2. 固定输出“今日完成 / 问题风险 / 明日计划”三段；问题风险为空时省略该段。
3. 可以调整句式、排序、关注角度和详略，但历史日报只用于避免重复，不能成为今日事实来源。
4. 用户反馈若明显是长期写作偏好，可提出一条 preference_suggestion；
   临时事实或本日报专属要求不要建议长期保存。
5. 只返回一个 JSON 对象，不要 Markdown 代码围栏：
{"reply":"简短说明","report":"完整日报 Markdown",
 "preference_suggestion":null或"一条长期偏好"}
"""


class DailyReportService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def get_profile(self, current_user: User) -> DailyReportProfileResponse:
        profile = await self._get_or_create_profile(current_user.id)
        return self._profile_response(profile)

    async def update_profile(
        self,
        payload: DailyReportProfileUpdateRequest,
        current_user: User,
    ) -> DailyReportProfileResponse:
        profile = await self._get_or_create_profile(current_user.id)
        self._require_profile_version(profile, payload.expected_version)
        profile.custom_prompt = payload.custom_prompt.strip()
        profile.prompt_version += 1
        self._add_prompt_version(profile, "用户手动编辑 Prompt")
        await self.session.commit()
        await self.session.refresh(profile)
        return self._profile_response(profile)

    async def reset_profile(self, current_user: User) -> DailyReportProfileResponse:
        profile = await self._get_or_create_profile(current_user.id)
        if profile.custom_prompt != DEFAULT_USER_PROMPT or profile.preferences:
            profile.custom_prompt = DEFAULT_USER_PROMPT
            profile.preferences = {}
            profile.prompt_version += 1
            self._add_prompt_version(profile, "恢复默认 Prompt")
            await self.session.commit()
            await self.session.refresh(profile)
        return self._profile_response(profile)

    async def accept_preference(
        self,
        payload: DailyReportPreferenceAcceptRequest,
        current_user: User,
    ) -> DailyReportProfileResponse:
        profile = await self._get_or_create_profile(current_user.id)
        self._require_profile_version(profile, payload.expected_version)
        requirement = " ".join(payload.requirement.split())
        prompt_lines = [
            line.rstrip() for line in profile.custom_prompt.splitlines() if line.strip()
        ]
        normalized_requirement = f"- {requirement}"
        if normalized_requirement not in prompt_lines:
            next_prompt = "\n".join([*prompt_lines, normalized_requirement]).strip()
            if len(next_prompt) > 6000:
                raise ValidationError(
                    "daily_report_prompt_too_long",
                    "定制 Prompt 已达到长度上限，请先合并或删除旧要求",
                )
            saved_requirements = profile.preferences.get("requirements", [])
            requirements = (
                [str(item) for item in saved_requirements if str(item).strip()]
                if isinstance(saved_requirements, list)
                else []
            )
            if requirement not in requirements:
                requirements.append(requirement)
            profile.custom_prompt = next_prompt
            profile.preferences = {
                **profile.preferences,
                "requirements": requirements[-50:],
            }
            profile.prompt_version += 1
            self._add_prompt_version(profile, f"保存长期偏好：{requirement[:120]}")
            await self.session.commit()
            await self.session.refresh(profile)
        return self._profile_response(profile)

    async def start_session(
        self,
        payload: DailyReportSessionStartRequest,
        current_user: User,
    ) -> DailyReportSessionResponse:
        self._require_work(payload)
        profile = await self._get_or_create_profile(current_user.id)
        input_data = payload.model_dump(mode="json")
        fallback_report = build_local_report(payload)
        history = await self._similar_history(current_user.id, fallback_report)
        messages = self._initial_provider_messages(profile, input_data, history)
        result = await self._generate_with_fallback(messages, fallback_report)

        report_session = DailyReportSession(
            user_id=current_user.id,
            work_date=payload.work_date,
            status="active",
            input_data=input_data,
            current_draft=result.report,
            prompt_version=profile.prompt_version,
            version=1,
            model_name=result.model_name,
            provider_mode=result.provider_mode,
        )
        self.session.add(report_session)
        await self.session.flush()
        self.session.add_all(
            [
                DailyReportMessage(
                    session_id=report_session.id,
                    user_id=current_user.id,
                    sequence=1,
                    role="user",
                    content=format_initial_message(payload),
                    message_metadata={},
                ),
                DailyReportMessage(
                    session_id=report_session.id,
                    user_id=current_user.id,
                    sequence=2,
                    role="assistant",
                    content=result.reply,
                    message_metadata=provider_metadata(result),
                ),
            ]
        )
        await self.session.commit()
        return await self.get_session(report_session.id, current_user)

    async def get_session(
        self,
        session_id: str,
        current_user: User,
    ) -> DailyReportSessionResponse:
        report_session = await self._require_session(session_id, current_user.id)
        messages = await self._messages(report_session.id, current_user.id)
        return DailyReportSessionResponse.from_model(report_session, messages)

    async def followup(
        self,
        session_id: str,
        payload: DailyReportSessionFollowupRequest,
        current_user: User,
    ) -> DailyReportSessionResponse:
        report_session = await self._require_session(session_id, current_user.id)
        self._require_active(report_session)
        self._require_session_version(report_session, payload.expected_version)
        profile = await self._get_or_create_profile(current_user.id)
        stored_messages = await self._messages(report_session.id, current_user.id)
        next_sequence = stored_messages[-1].sequence + 1 if stored_messages else 1
        base_draft = (payload.current_content or report_session.current_draft).strip()
        include_risks = bool(report_session.input_data.get("risks"))
        try:
            require_report_structure(base_draft, include_risks=include_risks)
        except AppError:
            base_draft = build_local_report(
                DailyReportInput.model_validate(report_session.input_data)
            )
        provider_messages = self._followup_provider_messages(
            profile,
            report_session,
            stored_messages,
            payload.message,
            base_draft,
        )
        result = await self._generate_with_fallback(
            provider_messages,
            base_draft,
        )
        self.session.add_all(
            [
                DailyReportMessage(
                    session_id=report_session.id,
                    user_id=current_user.id,
                    sequence=next_sequence,
                    role="user",
                    content=payload.message.strip(),
                    message_metadata={},
                ),
                DailyReportMessage(
                    session_id=report_session.id,
                    user_id=current_user.id,
                    sequence=next_sequence + 1,
                    role="assistant",
                    content=result.reply,
                    message_metadata=provider_metadata(result),
                ),
            ]
        )
        report_session.current_draft = result.report
        report_session.prompt_version = profile.prompt_version
        report_session.model_name = result.model_name
        report_session.provider_mode = result.provider_mode
        report_session.version += 1
        await self.session.commit()
        return await self.get_session(report_session.id, current_user)

    async def confirm(
        self,
        session_id: str,
        payload: DailyReportSessionConfirmRequest,
        current_user: User,
    ) -> DailyReportResponse:
        report_session = await self._require_session(session_id, current_user.id)
        existing = await self.session.scalar(
            select(DailyReport).where(
                DailyReport.session_id == report_session.id,
                DailyReport.user_id == current_user.id,
            )
        )
        if existing is not None:
            return DailyReportResponse.from_model(existing)
        self._require_active(report_session)
        self._require_session_version(report_session, payload.expected_version)
        content = payload.content.strip()
        report_session.current_draft = content
        report_session.status = "confirmed"
        report_session.version += 1
        report = DailyReport(
            user_id=current_user.id,
            session_id=report_session.id,
            work_date=report_session.work_date,
            content=content,
            source_input=report_session.input_data,
            prompt_version=report_session.prompt_version,
            model_name=report_session.model_name,
        )
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return DailyReportResponse.from_model(report)

    async def list_reports(self, current_user: User, limit: int = 30) -> list[DailyReportResponse]:
        reports = list(
            await self.session.scalars(
                select(DailyReport)
                .where(DailyReport.user_id == current_user.id)
                .order_by(desc(DailyReport.work_date), desc(DailyReport.created_at))
                .limit(limit)
            )
        )
        return [DailyReportResponse.from_model(report) for report in reports]

    async def delete_report(self, report_id: str, current_user: User) -> bool:
        report = await self.session.scalar(
            select(DailyReport).where(
                DailyReport.id == report_id,
                DailyReport.user_id == current_user.id,
            )
        )
        if report is None:
            raise NotFoundError("daily_report_not_found", "日报不存在")
        await self.session.execute(
            delete(DailyReportSession).where(
                DailyReportSession.id == report.session_id,
                DailyReportSession.user_id == current_user.id,
            )
        )
        await self.session.commit()
        return True

    async def clear_history(self, current_user: User) -> bool:
        await self.session.execute(
            delete(DailyReport).where(DailyReport.user_id == current_user.id)
        )
        await self.session.execute(
            delete(DailyReportSession).where(DailyReportSession.user_id == current_user.id)
        )
        await self.session.commit()
        return True

    async def _get_or_create_profile(self, user_id: str) -> DailyReportProfile:
        profile = await self.session.scalar(
            select(DailyReportProfile).where(DailyReportProfile.user_id == user_id)
        )
        if profile is not None:
            return profile
        profile = DailyReportProfile(
            user_id=user_id,
            custom_prompt=DEFAULT_USER_PROMPT,
            preferences={},
            prompt_version=1,
        )
        self.session.add(profile)
        await self.session.flush()
        self._add_prompt_version(profile, "创建默认 Prompt")
        await self.session.commit()
        await self.session.refresh(profile)
        return profile

    async def _require_session(self, session_id: str, user_id: str) -> DailyReportSession:
        report_session = await self.session.scalar(
            select(DailyReportSession).where(
                DailyReportSession.id == session_id,
                DailyReportSession.user_id == user_id,
            )
        )
        if report_session is None:
            raise NotFoundError("daily_report_session_not_found", "日报会话不存在")
        return report_session

    async def _messages(self, session_id: str, user_id: str) -> list[DailyReportMessage]:
        return list(
            await self.session.scalars(
                select(DailyReportMessage)
                .where(
                    DailyReportMessage.session_id == session_id,
                    DailyReportMessage.user_id == user_id,
                )
                .order_by(DailyReportMessage.sequence)
            )
        )

    async def _similar_history(self, user_id: str, current_text: str) -> list[str]:
        reports = list(
            await self.session.scalars(
                select(DailyReport)
                .where(DailyReport.user_id == user_id)
                .order_by(desc(DailyReport.created_at))
                .limit(30)
            )
        )
        ranked = sorted(
            ((text_similarity(current_text, report.content), report.content) for report in reports),
            key=lambda item: item[0],
            reverse=True,
        )
        return [content[:1600] for score, content in ranked[:3] if score > 0.08]

    async def _generate_with_fallback(
        self,
        messages: list[dict[str, str]],
        fallback_report: str,
    ) -> DailyReportProviderResult:
        provider, ai_enabled = configured_provider(self.settings)
        try:
            result = await provider.generate(messages, fallback_report=fallback_report)
            require_report_structure(
                result.report,
                include_risks="## 问题风险" in fallback_report,
            )
            return result
        except AppError:
            if not ai_enabled:
                raise
            return await LocalDailyReportProvider().generate(
                messages,
                fallback_report=fallback_report,
            )

    def _initial_provider_messages(
        self,
        profile: DailyReportProfile,
        input_data: dict[str, object],
        history: list[str],
    ) -> list[dict[str, str]]:
        context = {
            "personal_prompt": profile.custom_prompt,
            "current_facts": input_data,
            "similar_history_for_wording_avoidance": history,
        }
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "请生成本次日报。上下文：\n" + json.dumps(context, ensure_ascii=False),
            },
        ]

    def _followup_provider_messages(
        self,
        profile: DailyReportProfile,
        report_session: DailyReportSession,
        stored_messages: list[DailyReportMessage],
        feedback: str,
        current_draft: str,
    ) -> list[dict[str, str]]:
        context = {
            "personal_prompt": profile.custom_prompt,
            "current_facts": report_session.input_data,
        }
        messages: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "继续修改同一份日报。上下文：\n"
                + json.dumps(context, ensure_ascii=False),
            },
        ]
        for message in stored_messages[-10:]:
            messages.append({"role": message.role, "content": message.content})
        messages.extend(
            [
                {
                    "role": "assistant",
                    "content": "当前日报草稿：\n" + current_draft,
                },
                {"role": "user", "content": feedback.strip()},
            ]
        )
        return messages

    def _profile_response(self, profile: DailyReportProfile) -> DailyReportProfileResponse:
        _, ai_enabled = configured_provider(self.settings)
        return DailyReportProfileResponse.from_model(
            profile,
            ai_enabled=ai_enabled,
            provider_mode="ai" if ai_enabled else "local_fallback",
            model_name=(
                self.settings.daily_report_ai_model if ai_enabled else "local-daily-report-v1"
            ),
        )

    def _add_prompt_version(self, profile: DailyReportProfile, summary: str) -> None:
        self.session.add(
            DailyReportPromptVersion(
                profile_id=profile.id,
                user_id=profile.user_id,
                version=profile.prompt_version,
                custom_prompt=profile.custom_prompt,
                preferences=profile.preferences,
                change_summary=summary[:500],
            )
        )

    def _require_profile_version(self, profile: DailyReportProfile, expected: int) -> None:
        if profile.prompt_version != expected:
            raise ConflictError(
                "daily_report_prompt_conflict",
                "定制 Prompt 已在其他页面更新，请刷新后重试",
                details={"current_version": profile.prompt_version},
            )

    def _require_session_version(self, session: DailyReportSession, expected: int) -> None:
        if session.version != expected:
            raise ConflictError(
                "daily_report_session_conflict",
                "日报草稿已在其他页面更新，请刷新后重试",
                details={"current_version": session.version},
            )

    def _require_active(self, session: DailyReportSession) -> None:
        if session.status != "active":
            raise ConflictError("daily_report_session_confirmed", "该日报已经确认")

    def _require_work(self, payload: DailyReportInput) -> None:
        if not payload.recurring_work and not payload.extra_work:
            raise ValidationError(
                "daily_report_work_required",
                "请至少填写一项真实的常规工作或今日额外工作",
            )


def build_local_report(payload: DailyReportInput) -> str:
    completed = [*payload.recurring_work, *payload.extra_work]
    style_prefixes = {
        "concise": ("完成并跟进", "推进"),
        "detailed": ("围绕", "持续推进"),
        "result": ("聚焦实际进展，推进", "完成相关跟进："),
        "process": ("按计划开展", "梳理并推进"),
    }
    prefixes = style_prefixes[payload.style]
    lines = ["## 今日完成"]
    for index, item in enumerate(completed):
        prefix = prefixes[index % len(prefixes)]
        detail = f"「{item}」相关工作" if payload.style == "detailed" else f" {item}"
        lines.append(f"- {prefix}{detail}。")
    if payload.risks:
        lines.extend(["", "## 问题风险", *[f"- {item}" for item in payload.risks]])
    tomorrow = payload.tomorrow_plan or ["结合今日进展继续跟进相关事项"]
    lines.extend(["", "## 明日计划", *[f"- {item}" for item in tomorrow]])
    return "\n".join(lines)


def format_initial_message(payload: DailyReportInput) -> str:
    return "请根据以下真实工作生成日报：\n" + json.dumps(
        payload.model_dump(mode="json"),
        ensure_ascii=False,
    )


def provider_metadata(result: DailyReportProviderResult) -> dict[str, object]:
    return (
        {"preference_suggestion": result.preference_suggestion}
        if result.preference_suggestion
        else {}
    )


def normalized_char_ngrams(value: str, size: int = 3) -> set[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", value.lower())
    if len(normalized) <= size:
        return {normalized} if normalized else set()
    return {normalized[index : index + size] for index in range(len(normalized) - size + 1)}


def text_similarity(left: str, right: str) -> float:
    left_grams = normalized_char_ngrams(left)
    right_grams = normalized_char_ngrams(right)
    if not left_grams or not right_grams:
        return 0.0
    return len(left_grams & right_grams) / len(left_grams | right_grams)


def require_report_structure(report: str, *, include_risks: bool) -> None:
    completed_at = report.find("## 今日完成")
    risks_at = report.find("## 问题风险")
    tomorrow_at = report.find("## 明日计划")
    valid_order = completed_at >= 0 and tomorrow_at > completed_at
    valid_risks = (
        risks_at > completed_at and risks_at < tomorrow_at if include_risks else risks_at < 0
    )
    if not valid_order or not valid_risks:
        raise AppError(
            "daily_report_provider_invalid_structure",
            "日报模型没有按约定返回完整结构",
            status_code=503,
        )
