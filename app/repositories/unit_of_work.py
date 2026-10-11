from typing import Protocol

from app.repositories.files import FileRepository
from app.repositories.otp import OtpRepository
from app.repositories.tokens import RefreshTokenRepository
from app.repositories.users import UserRepository


class UnitOfWork(Protocol):
    users: UserRepository
    otps: OtpRepository
    tokens: RefreshTokenRepository
    files: FileRepository

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def __enter__(self) -> "UnitOfWork": ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> UnitOfWork: ...
