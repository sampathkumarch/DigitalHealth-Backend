from app.services.health import HealthService


def test_liveness_reports_process_up() -> None:
    service = HealthService(app_name="Health Backend", environment="test")

    report = service.liveness()

    assert report.status == "ok"
    assert report.app_name == "Health Backend"
    assert report.environment == "test"
