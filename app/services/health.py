from app.domain.health import HealthReport


class HealthService:
    """Reports whether this process is up."""

    def __init__(self, app_name: str, environment: str) -> None:
        self._app_name = app_name
        self._environment = environment

    def liveness(self) -> HealthReport:
        return HealthReport(
            status="ok",
            app_name=self._app_name,
            environment=self._environment,
        )
