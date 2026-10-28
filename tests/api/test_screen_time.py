from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_screen_time_service
from app.domain.users import new_member
from app.main import create_app
from app.services.screen_time import ScreenTimeService
from tests.unit.test_screen_time import DEVICE, Factory, MemoryScreenTime

NOW = datetime(2026, 10, 27, 8, 0, tzinfo=timezone.utc)


def _body(**overrides):
    values = {
        "device_id": str(DEVICE),
        "days": [
            {
                "local_date": "2026-10-27",
                "timezone": "Asia/Kolkata",
                "status": "partial",
                "screen_on_ms": 3_600_000,
                "hours": [3_600_000 if index == 10 else 0 for index in range(24)],
                "captured_at": "2026-10-27T08:00:00Z",
                "apps": [
                    {
                        "package_name": "com.whatsapp",
                        "label": "WhatsApp",
                        "visible_ms": 1_800_000,
                        "launch_count": 4,
                    }
                ],
            }
        ],
    }
    values.update(overrides)
    return values


def test_screen_time_requires_a_signed_in_user() -> None:
    client = TestClient(create_app())
    missing = client.put("/api/v1/me/screen-time/days", json=_body())
    assert missing.status_code == 401


def test_member_can_save_and_read_a_day() -> None:
    member = new_member("+91", "9876543210", NOW)
    service = ScreenTimeService(Factory(MemoryScreenTime()), clock=lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: member
    app.dependency_overrides[get_screen_time_service] = lambda: service
    client = TestClient(app)

    saved = client.put("/api/v1/me/screen-time/days", json=_body())
    assert saved.status_code == 200
    assert saved.json()["days"][0]["screen_on_ms"] == 3_600_000
    assert saved.json()["days"][0]["apps"][0]["label"] == "WhatsApp"
    assert len(saved.json()["days"][0]["hours"]) == 24

    listed = client.get(
        "/api/v1/me/screen-time",
        params={"device_id": str(DEVICE), "from": "2026-10-21", "to": "2026-10-27"},
    )
    assert listed.status_code == 200
    assert listed.json()["days"][0]["local_date"] == "2026-10-27"


def test_another_members_day_is_not_readable() -> None:
    owner = new_member("+91", "9876543210", NOW)
    other = new_member("+91", "9876543211", NOW)
    service = ScreenTimeService(Factory(MemoryScreenTime()), clock=lambda: NOW)
    app = create_app()
    app.dependency_overrides[get_screen_time_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: owner
    client = TestClient(app)
    client.put("/api/v1/me/screen-time/days", json=_body())

    app.dependency_overrides[get_current_user] = lambda: other
    listed = client.get(
        "/api/v1/me/screen-time",
        params={"device_id": str(DEVICE), "from": "2026-10-21", "to": "2026-10-27"},
    )
    assert listed.status_code == 200
    assert listed.json()["days"] == []
