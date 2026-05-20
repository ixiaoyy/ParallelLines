from __future__ import annotations

import asyncio
import smtplib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.message import EmailMessage

import structlog

from app.core.config import Settings
from app.core.exceptions import AppError

logger = structlog.get_logger("services.email")


@dataclass(frozen=True)
class OutboxEmail:
    to_email: str
    subject: str
    body: str
    verification_code: str
    kind: str
    sent_at: datetime


EMAIL_OUTBOX: list[OutboxEmail] = []


def clear_email_outbox() -> None:
    EMAIL_OUTBOX.clear()


def latest_verification_code(to_email: str) -> str | None:
    return latest_email_secret(to_email, kind="email_verification")


def latest_email_secret(to_email: str, *, kind: str) -> str | None:
    normalized_email = to_email.lower()
    for email in reversed(EMAIL_OUTBOX):
        if email.to_email.lower() == normalized_email and email.kind == kind:
            return email.verification_code
    return None


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send_verification_code(self, *, to_email: str, username: str, code: str) -> None:
        subject = "平行线注册验证码"
        body = (
            f"{username}，你好：\n\n"
            f"你的平行线注册验证码是：{code}\n"
            f"验证码将在 {self.settings.email_verification_code_ttl_minutes} 分钟后失效。\n\n"
            "如果这不是你本人操作，请忽略这封邮件。"
        )

        if self.settings.email_delivery_mode == "memory":
            self._send_to_memory(
                to_email=to_email,
                subject=subject,
                body=body,
                code=code,
                kind="email_verification",
            )
            return

        await self._send_via_smtp(to_email=to_email, subject=subject, body=body)

    async def send_password_reset(self, *, to_email: str, username: str, token: str) -> None:
        subject = "平行线密码重置"
        body = (
            f"{username}，你好：\n\n"
            "你正在重置平行线账号密码。\n"
            f"重置令牌：{token}\n"
            f"令牌将在 {self.settings.password_reset_token_ttl_minutes} 分钟后失效。\n\n"
            "如果这不是你本人操作，请忽略这封邮件。"
        )

        if self.settings.email_delivery_mode == "memory":
            self._send_to_memory(
                to_email=to_email,
                subject=subject,
                body=body,
                code=token,
                kind="password_reset",
            )
            return

        await self._send_via_smtp(to_email=to_email, subject=subject, body=body)

    async def send_email_change(self, *, to_email: str, username: str, token: str) -> None:
        subject = "平行线邮箱变更确认"
        body = (
            f"{username}，你好：\n\n"
            "请使用下面的令牌确认将平行线账号邮箱改为此地址。\n"
            f"确认令牌：{token}\n"
            f"令牌将在 {self.settings.email_change_token_ttl_minutes} 分钟后失效。\n\n"
            "如果这不是你本人操作，请忽略这封邮件。"
        )

        if self.settings.email_delivery_mode == "memory":
            self._send_to_memory(
                to_email=to_email,
                subject=subject,
                body=body,
                code=token,
                kind="email_change",
            )
            return

        await self._send_via_smtp(to_email=to_email, subject=subject, body=body)

    def _send_to_memory(
        self,
        *,
        to_email: str,
        subject: str,
        body: str,
        code: str,
        kind: str,
    ) -> None:
        if self.settings.environment == "production":
            raise AppError(
                "email_delivery_unavailable",
                "Email delivery is not configured",
                status_code=503,
            )
        EMAIL_OUTBOX.append(
            OutboxEmail(
                to_email=to_email,
                subject=subject,
                body=body,
                verification_code=code,
                kind=kind,
                sent_at=datetime.now(UTC),
            )
        )

    async def _send_via_smtp(self, *, to_email: str, subject: str, body: str) -> None:
        if not self.settings.smtp_host:
            raise AppError(
                "email_delivery_unavailable",
                "SMTP host is not configured",
                status_code=503,
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.settings.smtp_from_email
        message["To"] = to_email
        message.set_content(body)

        try:
            await asyncio.to_thread(self._send_smtp_message, message)
        except AppError:
            raise
        except (OSError, smtplib.SMTPException) as exc:
            logger.warning(
                "verification_email_failed",
                email_domain=to_email.rsplit("@", 1)[-1] if "@" in to_email else "unknown",
                error_type=type(exc).__name__,
            )
            raise AppError(
                "email_delivery_failed",
                "Verification email could not be sent",
                status_code=503,
            ) from exc

    def _send_smtp_message(self, message: EmailMessage) -> None:
        smtp_class = smtplib.SMTP_SSL if self.settings.smtp_use_ssl else smtplib.SMTP
        with smtp_class(
            self.settings.smtp_host,
            self.settings.smtp_port,
            timeout=self.settings.smtp_timeout_seconds,
        ) as smtp:
            if self.settings.smtp_use_tls and not self.settings.smtp_use_ssl:
                smtp.starttls()
            if self.settings.smtp_username:
                smtp.login(self.settings.smtp_username, self.settings.smtp_password or "")
            smtp.send_message(message)
