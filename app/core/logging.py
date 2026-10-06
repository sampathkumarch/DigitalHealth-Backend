import logging

from app.core.config import settings


def setup_logging() -> None:
    """Configure process logging once, from settings."""
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(settings.log_level)
        return

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
