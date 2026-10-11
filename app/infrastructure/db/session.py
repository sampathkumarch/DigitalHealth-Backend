from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.infrastructure.repositories.sql import (
    SqlFileRepository,
    SqlOtpRepository,
    SqlRefreshTokenRepository,
    SqlUserRepository,
)

_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is not None:
        return _engine
    kwargs: dict[str, object] = {"pool_pre_ping": True}
    if settings.db_pgbouncer:
        kwargs["poolclass"] = NullPool
        kwargs["connect_args"] = {"prepare_threshold": None}
    else:
        kwargs["pool_size"] = settings.db_pool_size
        kwargs["max_overflow"] = settings.db_max_overflow
        kwargs["pool_timeout"] = settings.db_pool_timeout
        kwargs["pool_recycle"] = settings.db_pool_recycle_seconds
    _engine = create_engine(settings.database_url, **kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


def ping_database() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))


class SqlUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self.session: Session | None = None
        self.users: SqlUserRepository
        self.otps: SqlOtpRepository
        self.tokens: SqlRefreshTokenRepository
        self.files: SqlFileRepository

    def __enter__(self) -> "SqlUnitOfWork":
        session = self._session_factory()
        self.session = session
        self.users = SqlUserRepository(session)
        self.otps = SqlOtpRepository(session)
        self.tokens = SqlRefreshTokenRepository(session)
        self.files = SqlFileRepository(session)
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.session is not None:
            if exc_type is not None:
                self.session.rollback()
            self.session.close()

    def commit(self) -> None:
        if self.session is not None:
            self.session.commit()

    def rollback(self) -> None:
        if self.session is not None:
            self.session.rollback()


class SqlUnitOfWorkFactory:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlUnitOfWork:
        return SqlUnitOfWork(self._session_factory)


def get_uow_factory() -> SqlUnitOfWorkFactory:
    return SqlUnitOfWorkFactory(get_session_factory())
