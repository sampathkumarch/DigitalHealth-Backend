from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.domain.roles import ADMIN
from app.domain.users import UserAccount
from app.infrastructure.db.session import get_uow_factory, ping_database
from app.infrastructure.redis.client import RedisRateLimiter, RedisTokenDenylist, get_redis, ping_redis
from app.infrastructure.security.jwt_tokens import JwtAccessTokens
from app.infrastructure.storage.factory import build_storage
from app.repositories.denylist import TokenDenylist
from app.repositories.rate_limit import RateLimiter
from app.repositories.storage import ObjectStorage
from app.repositories.tokens import AccessTokens
from app.repositories.unit_of_work import UnitOfWorkFactory
from app.services.auth import AuthConfig, AuthService
from app.services.diagnoses import DiagnosisService
from app.services.diseases import DiseaseCatalogService
from app.services.files import FileService
from app.services.health import HealthService
from app.services.profile import ProfileService
from app.services.readiness import ReadinessService
from app.services.screen_time import ScreenTimeService
from app.worker import CeleryOtpDispatcher

_bearer = HTTPBearer(auto_error=False)
_tokens: JwtAccessTokens | None = None
_limiter: RedisRateLimiter | None = None
_denylist: RedisTokenDenylist | None = None
_storage: ObjectStorage | None = None
_dispatcher = CeleryOtpDispatcher()


def get_health_service() -> HealthService:
    return HealthService(
        app_name=settings.app_name,
        environment=settings.app_env,
    )


def get_readiness_service() -> ReadinessService:
    return ReadinessService(ping_database, ping_redis)


def get_access_tokens() -> AccessTokens:
    global _tokens
    if _tokens is None:
        _tokens = JwtAccessTokens(
            settings.jwt_secret,
            settings.jwt_access_ttl_seconds,
            settings.s3_presign_ttl_seconds,
        )
    return _tokens


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = RedisRateLimiter(get_redis())
    return _limiter


def get_denylist() -> TokenDenylist:
    global _denylist
    if _denylist is None:
        _denylist = RedisTokenDenylist(get_redis())
    return _denylist


def get_storage() -> ObjectStorage:
    global _storage
    if _storage is None:
        _storage = build_storage(settings)
    return _storage


def get_auth_config() -> AuthConfig:
    return AuthConfig(
        otp_ttl_seconds=settings.otp_ttl_seconds,
        otp_length=settings.otp_length,
        otp_max_attempts=settings.otp_max_attempts,
        otp_resend_seconds=settings.otp_resend_seconds,
        otp_send_limit=settings.otp_send_limit,
        otp_send_window_seconds=settings.otp_send_window_seconds,
        otp_verify_limit=settings.otp_verify_limit,
        otp_store_plaintext=settings.otp_store_plaintext,
        otp_expose_in_response=settings.otp_expose_in_response,
        refresh_ttl_seconds=settings.jwt_refresh_ttl_seconds,
        otp_pepper=settings.otp_pepper,
        token_secret=settings.jwt_secret,
    )


def get_auth_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    limiter: RateLimiter = Depends(get_rate_limiter),
    tokens: AccessTokens = Depends(get_access_tokens),
    denylist: TokenDenylist = Depends(get_denylist),
    config: AuthConfig = Depends(get_auth_config),
) -> AuthService:
    return AuthService(
        uow_factory,
        limiter,
        _dispatcher,
        tokens,
        denylist,
        config,
    )


def get_profile_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ProfileService:
    return ProfileService(uow_factory)


def get_disease_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> DiseaseCatalogService:
    return DiseaseCatalogService(uow_factory)


def get_diagnosis_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> DiagnosisService:
    return DiagnosisService(uow_factory)


def get_screen_time_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ScreenTimeService:
    return ScreenTimeService(uow_factory)


def get_file_service(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    storage: ObjectStorage = Depends(get_storage),
    tokens: AccessTokens = Depends(get_access_tokens),
) -> FileService:
    return FileService(
        uow_factory,
        storage,
        tokens,
        max_bytes=settings.max_upload_bytes,
        public_base_url=settings.public_base_url,
        key_prefix=settings.s3_key_prefix,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    tokens: AccessTokens = Depends(get_access_tokens),
    denylist: TokenDenylist = Depends(get_denylist),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> UserAccount:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError()
    principal = tokens.decode_access(credentials.credentials)
    if denylist.denied(principal.jti):
        raise UnauthorizedError("Session ended")
    with uow_factory() as uow:
        user = uow.users.get_by_id(principal.user_id)
    if user is None or user.status != "active":
        raise UnauthorizedError()
    return user


def get_admin_user(user: UserAccount = Depends(get_current_user)) -> UserAccount:
    if user.role != ADMIN:
        raise ForbiddenError("Admin access is required.")
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    tokens: AccessTokens = Depends(get_access_tokens),
    denylist: TokenDenylist = Depends(get_denylist),
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> UserAccount | None:
    if credentials is None:
        return None
    try:
        return get_current_user(credentials, tokens, denylist, uow_factory)
    except UnauthorizedError:
        return None


def optional_bearer(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> HTTPAuthorizationCredentials | None:
    return credentials
