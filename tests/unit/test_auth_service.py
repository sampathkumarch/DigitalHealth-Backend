from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import (
    ConflictError,
    OtpExpired,
    OtpInvalid,
    OtpLocked,
    RateLimitError,
    UnauthorizedError,
    ValidationFailed,
)
from app.domain.profile import ProfileSubmission
from app.infrastructure.redis.memory import MemoryRateLimiter, MemoryTokenDenylist
from app.infrastructure.security.jwt_tokens import JwtAccessTokens
from app.services.auth import AuthConfig, AuthService
from app.services.profile import ProfileService
from tests.fakes import MemoryStore, MemoryUnitOfWorkFactory, RecordingDispatcher


class FrozenClock:
    def __init__(self) -> None:
        self.now = datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def _config() -> AuthConfig:
    return AuthConfig(
        otp_ttl_seconds=300,
        otp_length=6,
        otp_max_attempts=3,
        otp_resend_seconds=30,
        otp_send_limit=5,
        otp_send_window_seconds=900,
        otp_verify_limit=10,
        otp_store_plaintext=True,
        otp_expose_in_response=True,
        refresh_ttl_seconds=3600,
        otp_pepper="pepper",
        token_secret="token-secret",
    )


def _auth(store: MemoryStore | None = None):
    store = store or MemoryStore()
    clock = FrozenClock()
    limiter = MemoryRateLimiter()
    dispatcher = RecordingDispatcher()
    denylist = MemoryTokenDenylist()
    tokens = JwtAccessTokens("token-secret", 900, 900)
    service = AuthService(
        MemoryUnitOfWorkFactory(store),
        limiter,
        dispatcher,
        tokens,
        denylist,
        _config(),
        clock=clock,
    )
    return service, store, dispatcher, denylist, tokens, clock, limiter


def test_login_creates_member_and_sends_whatsapp() -> None:
    service, store, dispatcher, _denylist, _tokens, _clock_fn, _limiter = _auth()

    sent = service.send_login_otp("+91", "98765 43210")

    assert sent.debug_code is not None
    assert len(sent.debug_code) == 6
    assert dispatcher.whatsapp == [("+919876543210", sent.debug_code)]
    assert store.otps[0].code_plaintext == sent.debug_code
    assert store.otps[0].code_hash != sent.debug_code

    result = service.verify_login_otp("+91", "9876543210", sent.debug_code)

    assert result.is_new_user is True
    assert result.user.role == "member"
    assert result.user.phone == "9876543210"
    assert result.user.country_code == "+91"
    assert result.user.profile.profile_completed is False
    assert result.access_token
    assert result.refresh_token


def test_completed_profile_is_not_a_new_user() -> None:
    service, store, _dispatcher, _denylist, _tokens, clock, limiter = _auth()
    sent = service.send_login_otp("+91", "9876543210")
    assert sent.debug_code is not None
    first = service.verify_login_otp("+91", "9876543210", sent.debug_code)
    ProfileService(MemoryUnitOfWorkFactory(store)).update(
        first.user.id,
        ProfileSubmission(
            full_name="Rahul Sharma",
            email="rahul@example.com",
            date_of_birth="12/05/1998",
            weight_kg="72.5",
            blood_group="O+",
            conditions=("Diabetes",),
            other_condition="",
        ),
    )
    clock.advance(31)
    limiter.travel(31)
    resent = service.send_login_otp("+91", "9876543210")
    assert resent.debug_code is not None
    second = service.verify_login_otp("+91", "9876543210", resent.debug_code)

    assert second.is_new_user is False
    assert second.user.profile.full_name == "Rahul Sharma"
    assert second.user.profile.conditions == ("Diabetes",)
    assert second.user.email == "rahul@example.com"
    assert second.user.email_verified_at is None


def test_wrong_and_expired_otp() -> None:
    service, _store, _dispatcher, _denylist, _tokens, clock, limiter = _auth()
    service.send_login_otp("+91", "9876543210")

    with pytest.raises(OtpInvalid):
        service.verify_login_otp("+91", "9876543210", "000000")
    with pytest.raises(OtpInvalid):
        service.verify_login_otp("+91", "9876543210", "000000")
    with pytest.raises(OtpLocked):
        service.verify_login_otp("+91", "9876543210", "000000")

    clock.advance(31)
    limiter.travel(31)
    sent = service.send_login_otp("+91", "9876543210")
    clock.advance(301)
    assert sent.debug_code is not None
    with pytest.raises(OtpExpired):
        service.verify_login_otp("+91", "9876543210", sent.debug_code)


def test_resend_is_rate_limited() -> None:
    service, _store, _dispatcher, _denylist, _tokens, _clock_fn, _limiter = _auth()
    service.send_login_otp("+91", "9876543210")
    with pytest.raises(RateLimitError):
        service.send_login_otp("+91", "9876543210")


def test_refresh_rotation_revokes_reused_token() -> None:
    service, _store, _dispatcher, _denylist, _tokens, _clock_fn, _limiter = _auth()
    sent = service.send_login_otp("+91", "9876543210")
    assert sent.debug_code is not None
    first = service.verify_login_otp("+91", "9876543210", sent.debug_code)
    second = service.refresh(first.refresh_token)

    assert second.access_token
    with pytest.raises(UnauthorizedError):
        service.refresh(first.refresh_token)
    with pytest.raises(UnauthorizedError):
        service.refresh(second.refresh_token)


def test_logout_revokes_access_and_refresh() -> None:
    service, _store, _dispatcher, denylist, tokens, _clock_fn, _limiter = _auth()
    sent = service.send_login_otp("+91", "9876543210")
    assert sent.debug_code is not None
    result = service.verify_login_otp("+91", "9876543210", sent.debug_code)
    service.logout(result.access_token, result.refresh_token)

    principal = tokens.decode_access(result.access_token)
    assert denylist.denied(principal.jti)
    with pytest.raises(UnauthorizedError):
        service.refresh(result.refresh_token)


def test_email_verification_survives_profile_save() -> None:
    service, store, dispatcher, _denylist, _tokens, _clock_fn, _limiter = _auth()
    sent = service.send_login_otp("+91", "9876543210")
    assert sent.debug_code is not None
    result = service.verify_login_otp("+91", "9876543210", sent.debug_code)
    email_sent = service.send_email_otp(result.user, "Rahul@Example.com")
    assert email_sent.debug_code is not None
    assert dispatcher.email == [("rahul@example.com", email_sent.debug_code)]
    verified = service.verify_email_otp(result.user, "rahul@example.com", email_sent.debug_code)
    assert verified.email_verified_at is not None

    saved = ProfileService(MemoryUnitOfWorkFactory(store)).update(
        result.user.id,
        ProfileSubmission(
            full_name="Rahul Sharma",
            email="rahul@example.com",
            date_of_birth="",
            weight_kg="",
            blood_group="",
            conditions=(),
            other_condition="",
        ),
    )
    assert saved.email_verified_at is not None
    assert saved.profile.profile_completed is True


def test_email_taken_by_another_member() -> None:
    service, store, _dispatcher, _denylist, _tokens, clock, limiter = _auth()
    first_code = service.send_login_otp("+91", "9876543210").debug_code
    assert first_code is not None
    first = service.verify_login_otp("+91", "9876543210", first_code)
    ProfileService(MemoryUnitOfWorkFactory(store)).update(
        first.user.id,
        ProfileSubmission("Rahul Sharma", "rahul@example.com", "", "", "", (), ""),
    )
    clock.advance(31)
    limiter.travel(31)
    second_code = service.send_login_otp("+91", "9123456789").debug_code
    assert second_code is not None
    second = service.verify_login_otp("+91", "9123456789", second_code)
    with pytest.raises(ConflictError):
        service.send_email_otp(second.user, "rahul@example.com")


def test_invalid_phone_rejected() -> None:
    service, _store, _dispatcher, _denylist, _tokens, _clock_fn, _limiter = _auth()
    with pytest.raises(ValidationFailed):
        service.send_login_otp("+91", "12345")
