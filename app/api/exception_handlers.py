import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def _envelope(
    request: Request,
    *,
    code: str,
    message: str,
    details: object | None = None,
) -> dict[str, object]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(application: FastAPI) -> None:
    @application.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        response = JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                request,
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            response.headers["Retry-After"] = str(retry_after)
        return response

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, code="http_error", message=detail),
        )

    @application.exception_handler(RequestValidationError)
    async def validation_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_envelope(
                request,
                code="validation_error",
                message="Request validation failed",
                details=jsonable_encoder(exc.errors()),
            ),
        )

    @application.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        message = str(exc) if settings.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content=_envelope(request, code="internal_error", message=message),
        )
