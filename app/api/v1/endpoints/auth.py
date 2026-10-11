from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import get_auth_service, get_file_service, optional_bearer
from app.core.exceptions import UnauthorizedError
from app.schemas.auth import (
    AuthResponse,
    LogoutRequest,
    RefreshRequest,
    SendOtpRequest,
    SendOtpResponse,
    VerifyOtpRequest,
    build_auth,
)
from app.services.auth import AuthService
from app.services.files import FileService

router = APIRouter()


@router.post("/otp", response_model=SendOtpResponse)
def send_login_otp(
    body: SendOtpRequest,
    service: AuthService = Depends(get_auth_service),
) -> SendOtpResponse:
    result = service.send_login_otp(body.country_code, body.phone)
    return SendOtpResponse(
        expires_in=result.expires_in,
        resend_after=result.resend_after,
        debug_code=result.debug_code,
    )


@router.post("/otp/verify", response_model=AuthResponse)
def verify_login_otp(
    body: VerifyOtpRequest,
    service: AuthService = Depends(get_auth_service),
    files: FileService = Depends(get_file_service),
) -> AuthResponse:
    result = service.verify_login_otp(body.country_code, body.phone, body.code)
    return build_auth(result, files.url_for(result.user.profile.photo_file_id))


@router.post("/token/refresh", response_model=AuthResponse)
def refresh_session(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
    files: FileService = Depends(get_file_service),
) -> AuthResponse:
    result = service.refresh(body.refresh_token)
    return build_auth(result, files.url_for(result.user.profile.photo_file_id))


@router.post("/logout", status_code=204)
def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer),
    service: AuthService = Depends(get_auth_service),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError()
    service.logout(credentials.credentials, body.refresh_token)
