from dataclasses import dataclass


@dataclass(frozen=True)
class HealthReport:
    status: str
    app_name: str
    environment: str
