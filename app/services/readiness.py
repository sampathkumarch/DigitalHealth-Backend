import logging
from dataclasses import dataclass
from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReadinessReport:
    status: str
    database: str
    redis: str


class ReadinessService:
    def __init__(self, ping_db: Callable[[], None], ping_redis: Callable[[], None]) -> None:
        self._ping_db = ping_db
        self._ping_redis = ping_redis

    def check(self) -> ReadinessReport:
        database = _probe(self._ping_db)
        redis = _probe(self._ping_redis)
        status = "ok" if database == "up" and redis == "up" else "degraded"
        return ReadinessReport(status=status, database=database, redis=redis)


def _probe(fn: Callable[[], None]) -> str:
    try:
        fn()
    except Exception:
        logger.exception("readiness probe failed")
        return "down"
    return "up"
