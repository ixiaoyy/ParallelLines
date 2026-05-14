from typing import Any


class AppError(Exception):
    """Base typed domain/application error."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, code: str = "not_found", message: str = "Resource not found") -> None:
        super().__init__(code, message, status_code=404)


class PermissionDeniedError(AppError):
    def __init__(self, code: str = "permission_denied", message: str = "Permission denied") -> None:
        super().__init__(code, message, status_code=403)


class AuthenticationError(AppError):
    def __init__(
        self,
        code: str = "authentication_required",
        message: str = "Authentication required",
    ) -> None:
        super().__init__(code, message, status_code=401)


class ConflictError(AppError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, status_code=409, details=details)


class RateLimitError(AppError):
    def __init__(self, code: str = "rate_limited", message: str = "Too many requests") -> None:
        super().__init__(code, message, status_code=429)


class ValidationError(AppError):
    def __init__(
        self,
        code: str = "validation_error",
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, status_code=422, details=details)
