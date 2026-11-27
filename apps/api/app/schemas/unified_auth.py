"""统一浏览器登录协议；请求只接受固定用途字段，返回永不包含主站刷新令牌。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.users import UserPublic


class UnifiedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UnifiedBootstrapRequest(UnifiedRequest):
    # 只有主站完成真实登录后显式替换；普通旧本地状态不得反向覆盖中央会话。
    replace: bool = False


class UnifiedStateResponse(BaseModel):
    authenticated: bool
    subject: str | None = None
    auth_epoch: str | None = None


class UnifiedAccessResponse(UnifiedStateResponse):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    session_id: str
    user: UserPublic


class UnifiedAuthorizeRequest(UnifiedRequest):
    client_id: Literal["parallellines-circle", "parallellines-games"]
    redirect_uri: str = Field(max_length=512)
    state: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    code_challenge: str = Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")
    code_challenge_method: Literal["S256"]


class UnifiedAuthorizeResponse(BaseModel):
    redirect_url: str


class UnifiedExchangeRequest(UnifiedRequest):
    client_id: Literal["parallellines-circle", "parallellines-games"]
    redirect_uri: str = Field(max_length=512)
    code: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    code_verifier: str = Field(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9._~-]+$")


class UnifiedLogoutTicketRequest(UnifiedRequest):
    return_uri: str = Field(max_length=512)


class UnifiedBridgeLogoutRequest(UnifiedLogoutTicketRequest):
    client_id: Literal["parallellines-chat"]
    binding_id: str = Field(min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


class UnifiedLogoutTicketResponse(BaseModel):
    logout_url: str
    expires_in: int


class UnifiedLogoutRequest(UnifiedRequest):
    ticket: str | None = Field(
        default=None, min_length=32, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )


class UnifiedLogoutResponse(UnifiedStateResponse):
    ok: bool = True
    return_url: str | None = None
