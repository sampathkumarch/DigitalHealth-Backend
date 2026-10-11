from app.infrastructure.db import models  # noqa: F401
from app.infrastructure.db.base import Base


def test_account_tables_are_separated() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "user_profiles",
        "user_conditions",
        "files",
        "otp_challenges",
        "refresh_tokens",
    }
