class AppError(Exception):
    """Base error for failures the application knows how to explain."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "app_error",
        status_code: int = 400,
        details: object | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, code="conflict", status_code=409)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, code="unauthorized", status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(message, code="forbidden", status_code=403)


class ValidationFailed(AppError):
    def __init__(self, message: str, fields: dict[str, str] | None = None) -> None:
        details = {"fields": fields} if fields else None
        super().__init__(
            message,
            code="validation_error",
            status_code=422,
            details=details,
        )


class RateLimitError(AppError):
    def __init__(
        self,
        message: str = "Too many requests. Try again shortly.",
        *,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, code="rate_limited", status_code=429)
        self.retry_after = retry_after


class ServiceUnavailable(AppError):
    def __init__(self, message: str = "Service temporarily unavailable.") -> None:
        super().__init__(message, code="unavailable", status_code=503)


class OtpInvalid(AppError):
    def __init__(self) -> None:
        super().__init__(
            "That code is incorrect. Try again.",
            code="otp_invalid",
            status_code=400,
        )


class OtpExpired(AppError):
    def __init__(self) -> None:
        super().__init__(
            "This code has expired. Request a new one.",
            code="otp_expired",
            status_code=400,
        )


class OtpLocked(AppError):
    def __init__(self) -> None:
        super().__init__(
            "Too many attempts. Request a new code.",
            code="otp_locked",
            status_code=400,
        )
