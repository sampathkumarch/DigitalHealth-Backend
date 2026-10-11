from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

from app.core.exceptions import UnauthorizedError
from app.repositories.tokens import AccessPrincipal, IssuedAccess

_ALGORITHM = "HS256"


class JwtAccessTokens:
    def __init__(self, secret: str, access_ttl_seconds: int, file_ttl_seconds: int) -> None:
        self._secret = secret
        self._access_ttl = access_ttl_seconds
        self._file_ttl = file_ttl_seconds

    def issue_access(self, user_id: UUID) -> IssuedAccess:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=self._access_ttl)
        jti = str(uuid4())
        token = jwt.encode(
            {
                "sub": str(user_id),
                "jti": jti,
                "typ": "access",
                "iat": int(now.timestamp()),
                "exp": expires_at,
            },
            self._secret,
            algorithm=_ALGORITHM,
        )
        return IssuedAccess(
            value=token,
            jti=jti,
            expires_in=self._access_ttl,
            expires_at=expires_at,
        )

    def decode_access(self, token: str) -> AccessPrincipal:
        payload = self._decode(token, expected_type="access")
        return AccessPrincipal(
            user_id=UUID(payload["sub"]),
            jti=str(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )

    def issue_file_access(self, file_id: UUID) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {
                "sub": str(file_id),
                "typ": "file",
                "iat": int(now.timestamp()),
                "exp": now + timedelta(seconds=self._file_ttl),
            },
            self._secret,
            algorithm=_ALGORITHM,
        )

    def decode_file_access(self, token: str) -> UUID:
        payload = self._decode(token, expected_type="file")
        return UUID(payload["sub"])

    def _decode(self, token: str, *, expected_type: str) -> dict[str, object]:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid access token") from exc
        if payload.get("typ") != expected_type or "sub" not in payload:
            raise UnauthorizedError("Invalid access token")
        return payload
