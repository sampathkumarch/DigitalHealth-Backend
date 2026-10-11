import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    OtpExpired,
    OtpInvalid,
    OtpLocked,
    UnauthorizedError,
    ValidationFailed,
)
from app.core.security import generate_otp, generate_refresh_token, hash_code
from app.domain.errors import DomainError
from app.domain.otp import EMAIL, EMAIL_VERIFICATION, LOGIN, WHATSAPP, OtpChallenge
from app.domain.phone import normalize_phone
from app.domain.profile import require_email
from app.domain.tokens import RefreshToken
from app.domain.users import UserAccount, new_member
from app.repositories.denylist import TokenDenylist
from app.repositories.messaging import OtpDispatcher
from app.repositories.rate_limit import RateLimiter
from app.repositories.tokens import AccessTokens
from app.repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory


@dataclass(frozen=True)
class AuthConfig:
    otp_ttl_seconds: int
    otp_length: int
    otp_max_attempts: int
    otp_resend_seconds: int
    otp_send_limit: int
    otp_send_window_seconds: int
    otp_verify_limit: int
    otp_store_plaintext: bool
    otp_expose_in_response: bool
    refresh_ttl_seconds: int
    otp_pepper: str
    token_secret: str


@dataclass(frozen=True)
class SendOtpResult:
    expires_in: int
    resend_after: int
    debug_code: str | None


@dataclass(frozen=True)
class AuthResult:
    access_token: str
    refresh_token: str
    expires_in: int
    is_new_user: bool
    user: UserAccount


class AuthService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        limiter: RateLimiter,
        dispatcher: OtpDispatcher,
        tokens: AccessTokens,
        denylist: TokenDenylist,
        config: AuthConfig,
        clock=None,
    ) -> None:
        self._uow_factory = uow_factory
        self._limiter = limiter
        self._dispatcher = dispatcher
        self._tokens = tokens
        self._denylist = denylist
        self._config = config
        self._clock = clock or _utcnow

    def send_login_otp(self, country_code: str, phone: str) -> SendOtpResult:
        number = _phone(country_code, phone)
        self._hit_send(f"otp:login:{number.e164}")
        now = self._clock()
        with self._uow_factory() as uow:
            existing = uow.users.get_by_phone(number.country_code, number.national)
            code = self._store_otp(
                uow,
                channel=WHATSAPP,
                destination=number.e164,
                purpose=LOGIN,
                user_id=existing.id if existing else None,
                now=now,
            )
            uow.commit()
        self._dispatcher.dispatch_whatsapp(number.e164, code)
        return self._sent(code)

    def verify_login_otp(self, country_code: str, phone: str, code: str) -> AuthResult:
        number = _phone(country_code, phone)
        self._hit_verify(f"otp:login:{number.e164}")
        now = self._clock()
        code_hash = hash_code(code.strip(), self._config.otp_pepper)
        with self._uow_factory() as uow:
            challenge = uow.otps.get_latest(
                channel=WHATSAPP,
                destination=number.e164,
                purpose=LOGIN,
            )
            self._reject_or_consume(uow, challenge, code_hash, now)
            user = uow.users.get_by_phone(number.country_code, number.national)
            if user is not None and user.status != "active":
                uow.commit()
                raise ForbiddenError("This account is disabled.")
            if user is None:
                user = new_member(number.country_code, number.national, now)
                uow.users.add(user)
            else:
                user.phone_verified_at = now
                user.updated_at = now
                uow.users.save(user)
            raw_refresh, stored = self._new_refresh(user.id, now)
            uow.tokens.add(stored)
            uow.commit()
        access = self._tokens.issue_access(user.id)
        return AuthResult(
            access_token=access.value,
            refresh_token=raw_refresh,
            expires_in=access.expires_in,
            is_new_user=not user.profile.profile_completed,
            user=user,
        )

    def send_email_otp(self, user: UserAccount, email: str) -> SendOtpResult:
        address = _email(email)
        self._hit_send(f"otp:email:{user.id}")
        with self._uow_factory() as uow:
            owner = uow.users.get_by_email(address)
            if owner is not None and owner.id != user.id:
                raise ConflictError("That email is already in use.")
            code = self._store_otp(
                uow,
                channel=EMAIL,
                destination=address,
                purpose=EMAIL_VERIFICATION,
                user_id=user.id,
                now=self._clock(),
            )
            uow.commit()
        self._dispatcher.dispatch_email(address, code)
        return self._sent(code)

    def verify_email_otp(self, user: UserAccount, email: str, code: str) -> UserAccount:
        address = _email(email)
        self._hit_verify(f"otp:email:{user.id}")
        now = self._clock()
        code_hash = hash_code(code.strip(), self._config.otp_pepper)
        with self._uow_factory() as uow:
            fresh = uow.users.get_by_id(user.id)
            if fresh is None:
                raise UnauthorizedError()
            challenge = uow.otps.get_latest(
                channel=EMAIL,
                destination=address,
                purpose=EMAIL_VERIFICATION,
            )
            self._reject_or_consume(uow, challenge, code_hash, now)
            owner = uow.users.get_by_email(address)
            if owner is not None and owner.id != fresh.id:
                uow.commit()
                raise ConflictError("That email is already in use.")
            fresh.email = address
            fresh.email_verified_at = now
            fresh.updated_at = now
            uow.users.save(fresh)
            uow.commit()
            return fresh

    def refresh(self, refresh_token: str) -> AuthResult:
        now = self._clock()
        token_hash = hash_code(refresh_token, self._config.token_secret)
        with self._uow_factory() as uow:
            stored = uow.tokens.get_by_hash(token_hash)
            if stored is None or stored.expires_at <= now:
                raise UnauthorizedError("Invalid refresh token")
            if stored.revoked_at is not None:
                uow.tokens.revoke_all(stored.user_id, now)
                uow.commit()
                raise UnauthorizedError("Session ended")
            user = uow.users.get_by_id(stored.user_id)
            if user is None or user.status != "active":
                raise UnauthorizedError("Invalid refresh token")
            raw_refresh, replacement = self._new_refresh(user.id, now)
            stored.revoked_at = now
            stored.replaced_by_id = replacement.id
            uow.tokens.save(stored)
            uow.tokens.add(replacement)
            uow.commit()
        access = self._tokens.issue_access(user.id)
        return AuthResult(
            access_token=access.value,
            refresh_token=raw_refresh,
            expires_in=access.expires_in,
            is_new_user=not user.profile.profile_completed,
            user=user,
        )

    def logout(self, access_token: str, refresh_token: str | None) -> None:
        principal = self._tokens.decode_access(access_token)
        ttl = int((principal.expires_at - self._clock()).total_seconds())
        self._denylist.deny(principal.jti, ttl)
        if not refresh_token:
            return
        token_hash = hash_code(refresh_token, self._config.token_secret)
        now = self._clock()
        with self._uow_factory() as uow:
            stored = uow.tokens.get_by_hash(token_hash)
            if (
                stored is not None
                and stored.user_id == principal.user_id
                and stored.revoked_at is None
            ):
                stored.revoked_at = now
                uow.tokens.save(stored)
                uow.commit()

    def _store_otp(
        self,
        uow: UnitOfWork,
        *,
        channel: str,
        destination: str,
        purpose: str,
        user_id: UUID | None,
        now: datetime,
    ) -> str:
        code = generate_otp(self._config.otp_length)
        uow.otps.invalidate_active(
            channel=channel,
            destination=destination,
            purpose=purpose,
            now=now,
        )
        uow.otps.add(
            OtpChallenge(
                id=uuid4(),
                user_id=user_id,
                channel=channel,
                destination=destination,
                purpose=purpose,
                code_hash=hash_code(code, self._config.otp_pepper),
                code_plaintext=code if self._config.otp_store_plaintext else None,
                expires_at=now + timedelta(seconds=self._config.otp_ttl_seconds),
                attempt_count=0,
                max_attempts=self._config.otp_max_attempts,
                consumed_at=None,
                created_at=now,
            )
        )
        return code

    def _reject_or_consume(
        self,
        uow: UnitOfWork,
        challenge: OtpChallenge | None,
        code_hash: str,
        now: datetime,
    ) -> None:
        if challenge is None or challenge.consumed_at is not None:
            raise OtpInvalid()
        if challenge.is_expired(now):
            raise OtpExpired()
        if challenge.is_locked():
            raise OtpLocked()
        if not hmac.compare_digest(challenge.code_hash, code_hash):
            challenge.attempt_count += 1
            uow.otps.save(challenge)
            uow.commit()
            if challenge.is_locked():
                raise OtpLocked()
            raise OtpInvalid()
        if not uow.otps.consume(challenge.id, now):
            raise OtpInvalid()

    def _new_refresh(self, user_id: UUID, now: datetime) -> tuple[str, RefreshToken]:
        raw = generate_refresh_token()
        stored = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=hash_code(raw, self._config.token_secret),
            expires_at=now + timedelta(seconds=self._config.refresh_ttl_seconds),
            revoked_at=None,
            replaced_by_id=None,
            created_at=now,
        )
        return raw, stored

    def _sent(self, code: str) -> SendOtpResult:
        return SendOtpResult(
            expires_in=self._config.otp_ttl_seconds,
            resend_after=self._config.otp_resend_seconds,
            debug_code=code if self._config.otp_expose_in_response else None,
        )

    def _hit_send(self, scope: str) -> None:
        self._limiter.hit(
            f"{scope}:cooldown",
            limit=1,
            window_seconds=self._config.otp_resend_seconds,
            message="Please wait before requesting another code.",
        )
        self._limiter.hit(
            f"{scope}:window",
            limit=self._config.otp_send_limit,
            window_seconds=self._config.otp_send_window_seconds,
            message="Too many requests. Try again shortly.",
        )

    def _hit_verify(self, scope: str) -> None:
        self._limiter.hit(
            f"{scope}:verify",
            limit=self._config.otp_verify_limit,
            window_seconds=self._config.otp_send_window_seconds,
            message="Too many requests. Try again shortly.",
        )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _phone(country_code: str, phone: str):
    try:
        return normalize_phone(country_code, phone)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc


def _email(email: str) -> str:
    try:
        return require_email(email)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc
