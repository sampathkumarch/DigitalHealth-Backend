from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.profile import format_dob, format_weight
from app.domain.users import UserAccount
from app.services.auth import AuthResult


class SendOtpRequest(BaseModel):
    phone: str
    country_code: str = "+91"


class VerifyOtpRequest(BaseModel):
    phone: str
    country_code: str = "+91"
    code: str = Field(min_length=1, max_length=12)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class EmailOtpRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    email: str
    code: str = Field(min_length=1, max_length=12)


class SendOtpResponse(BaseModel):
    expires_in: int
    resend_after: int
    debug_code: str | None = None


class ProfileResponse(BaseModel):
    full_name: str
    email: str
    email_verified: bool
    verified_email: str
    date_of_birth: str
    weight_kg: str
    blood_group: str
    conditions: list[str]
    other_condition: str
    photo_file_id: UUID | None
    photo_url: str | None
    phone: str
    country_code: str
    profile_completed: bool


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    is_new_user: bool
    user_id: UUID
    role: str
    profile: ProfileResponse


class MeResponse(BaseModel):
    id: UUID
    role: str
    profile: ProfileResponse


def build_profile(user: UserAccount, photo_url: str | None) -> ProfileResponse:
    profile = user.profile
    verified = bool(user.email) and user.email_verified_at is not None
    return ProfileResponse(
        full_name=profile.full_name,
        email=user.email or "",
        email_verified=verified,
        verified_email=user.email if verified and user.email else "",
        date_of_birth=format_dob(profile.date_of_birth),
        weight_kg=format_weight(profile.weight_kg),
        blood_group=profile.blood_group or "",
        conditions=list(profile.conditions),
        other_condition=profile.other_condition,
        photo_file_id=profile.photo_file_id,
        photo_url=photo_url,
        phone=user.phone,
        country_code=user.country_code,
        profile_completed=profile.profile_completed,
    )


def build_auth(result: AuthResult, photo_url: str | None) -> AuthResponse:
    return AuthResponse(
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
        is_new_user=result.is_new_user,
        user_id=result.user.id,
        role=result.user.role,
        profile=build_profile(result.user, photo_url),
    )


def build_me(user: UserAccount, photo_url: str | None) -> MeResponse:
    return MeResponse(id=user.id, role=user.role, profile=build_profile(user, photo_url))
