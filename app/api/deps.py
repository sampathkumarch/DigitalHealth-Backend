from app.core.config import settings
from app.services.health import HealthService


def get_health_service() -> HealthService:
    return HealthService(
        app_name=settings.app_name,
        environment=settings.app_env,
    )
