from fastapi import APIRouter, Depends, File, UploadFile

from app.api.deps import get_auth_service, get_current_user, get_file_service, get_profile_service
from app.core.config import settings
from app.core.exceptions import ValidationFailed
from app.domain.users import UserAccount
from app.schemas.auth import (
    EmailOtpRequest,
    MeResponse,
    SendOtpResponse,
    VerifyEmailRequest,
    build_me,
)
from app.schemas.files import PhotoUploadResponse, StoredFileResponse
from app.schemas.profile import ProfileUpdateRequest
from app.services.auth import AuthService
from app.services.files import FileService
from app.services.profile import ProfileService

router = APIRouter()


@router.get("/me", response_model=MeResponse)
def read_me(
    user: UserAccount = Depends(get_current_user),
    files: FileService = Depends(get_file_service),
) -> MeResponse:
    return build_me(user, files.url_for(user.profile.photo_file_id))


@router.put("/me", response_model=MeResponse)
def update_me(
    body: ProfileUpdateRequest,
    user: UserAccount = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
    files: FileService = Depends(get_file_service),
) -> MeResponse:
    updated = service.update(user.id, body.submission())
    return build_me(updated, files.url_for(updated.profile.photo_file_id))


@router.post("/me/email/otp", response_model=SendOtpResponse)
def send_email_otp(
    body: EmailOtpRequest,
    user: UserAccount = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> SendOtpResponse:
    result = service.send_email_otp(user, body.email)
    return SendOtpResponse(
        expires_in=result.expires_in,
        resend_after=result.resend_after,
        debug_code=result.debug_code,
    )


@router.post("/me/email/otp/verify", response_model=MeResponse)
def verify_email_otp(
    body: VerifyEmailRequest,
    user: UserAccount = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    files: FileService = Depends(get_file_service),
) -> MeResponse:
    updated = service.verify_email_otp(user, body.email, body.code)
    return build_me(updated, files.url_for(updated.profile.photo_file_id))


@router.post("/me/photo", response_model=PhotoUploadResponse)
def upload_photo(
    file: UploadFile = File(...),
    user: UserAccount = Depends(get_current_user),
    service: FileService = Depends(get_file_service),
) -> PhotoUploadResponse:
    data = _read_limited(file, settings.max_upload_bytes)
    stored, updated = service.save_profile_photo(
        user.id,
        filename=file.filename or "photo",
        data=data,
    )
    profile = build_me(updated, service.url_for(updated.profile.photo_file_id)).profile
    return PhotoUploadResponse(
        file=StoredFileResponse(
            id=stored.id,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            width=stored.width,
            height=stored.height,
        ),
        profile=profile,
    )


def _read_limited(upload: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = upload.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise ValidationFailed(
                "Image must be 5 MB or smaller.",
                {"file": "Image must be 5 MB or smaller."},
            )
        chunks.append(chunk)
    return b"".join(chunks)
