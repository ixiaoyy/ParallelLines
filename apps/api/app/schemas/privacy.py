from pydantic import BaseModel, Field


class PrivacyActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PrivacyActionResponse(BaseModel):
    user_id: str
    username: str
    email: str
    status: str
    anonymized: bool
    reason: str | None = None
    revoked_sessions: int = 0
    deleted_security_tokens: int = 0
    deleted_recovery_codes: int = 0
    deleted_email_codes: int = 0
    deleted_drafts: int = 0
    deleted_notifications: int = 0
    removed_relationships: int = 0
    removed_board_memberships: int = 0
    removed_board_invitations: int = 0
    removed_private_message_participations: int = 0
    disabled_api_keys: int = 0
    disabled_webhooks: int = 0
    deleted_uploads: int = 0
    retained_uploads: int = 0
    anonymized_logs: int = 0


class RetentionPolicyResponse(BaseModel):
    user_export_available: bool
    account_deletion_mode: str
    retained_content: str
    removed_private_data: str
    export_redaction: str
    upload_retention: str
