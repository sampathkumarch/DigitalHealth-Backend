from datetime import datetime
from uuid import UUID

from app.domain.files import StoredFile
from app.domain.otp import OtpChallenge
from app.domain.tokens import RefreshToken
from app.domain.users import UserAccount
from app.repositories.errors import DuplicateRecord


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[UUID, UserAccount] = {}
        self.otps: list[OtpChallenge] = []
        self.tokens: dict[UUID, RefreshToken] = {}
        self.files: dict[UUID, StoredFile] = {}


class MemoryUsers:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self._store.users.get(user_id)

    def get_by_phone(self, country_code: str, phone: str) -> UserAccount | None:
        for user in self._store.users.values():
            if user.country_code == country_code and user.phone == phone:
                return user
        return None

    def get_by_email(self, email: str) -> UserAccount | None:
        for user in self._store.users.values():
            if user.email == email:
                return user
        return None

    def add(self, user: UserAccount) -> None:
        if self.get_by_phone(user.country_code, user.phone) is not None:
            raise DuplicateRecord("phone")
        if user.email and self.get_by_email(user.email) is not None:
            raise DuplicateRecord("email")
        self._store.users[user.id] = user

    def save(self, user: UserAccount) -> None:
        owner = self.get_by_email(user.email) if user.email else None
        if owner is not None and owner.id != user.id:
            raise DuplicateRecord("email")
        self._store.users[user.id] = user


class MemoryOtps:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, challenge: OtpChallenge) -> None:
        self._store.otps.append(challenge)

    def save(self, challenge: OtpChallenge) -> None:
        return None

    def get_latest(self, *, channel: str, destination: str, purpose: str) -> OtpChallenge | None:
        matches = [
            item
            for item in self._store.otps
            if item.channel == channel and item.destination == destination and item.purpose == purpose
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def invalidate_active(self, *, channel: str, destination: str, purpose: str, now: datetime) -> None:
        for item in self._store.otps:
            if (
                item.channel == channel
                and item.destination == destination
                and item.purpose == purpose
                and item.consumed_at is None
            ):
                item.consumed_at = now

    def consume(self, challenge_id: UUID, now: datetime) -> bool:
        for item in self._store.otps:
            if item.id == challenge_id:
                if item.consumed_at is not None:
                    return False
                item.consumed_at = now
                return True
        return False


class MemoryTokens:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, token: RefreshToken) -> None:
        self._store.tokens[token.id] = token

    def save(self, token: RefreshToken) -> None:
        self._store.tokens[token.id] = token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._store.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    def revoke_all(self, user_id: UUID, now: datetime) -> None:
        for token in self._store.tokens.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = now


class MemoryFiles:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, stored: StoredFile) -> None:
        self._store.files[stored.id] = stored

    def get(self, file_id: UUID) -> StoredFile | None:
        return self._store.files.get(file_id)


class MemoryUnitOfWork:
    def __init__(self, store: MemoryStore) -> None:
        self.users = MemoryUsers(store)
        self.otps = MemoryOtps(store)
        self.tokens = MemoryTokens(store)
        self.files = MemoryFiles(store)

    def __enter__(self) -> "MemoryUnitOfWork":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class MemoryUnitOfWorkFactory:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def __call__(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.store)


class RecordingDispatcher:
    def __init__(self) -> None:
        self.whatsapp: list[tuple[str, str]] = []
        self.email: list[tuple[str, str]] = []

    def dispatch_whatsapp(self, phone_e164: str, code: str) -> None:
        self.whatsapp.append((phone_e164, code))

    def dispatch_email(self, email: str, code: str) -> None:
        self.email.append((email, code))
