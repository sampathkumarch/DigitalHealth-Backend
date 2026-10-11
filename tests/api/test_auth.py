from fastapi.testclient import TestClient

from app.api.deps import get_auth_service, get_file_service
from app.main import create_app
from tests.unit.test_auth_service import _auth


class _NullFiles:
    def url_for(self, file_id: object) -> None:
        return None


def test_otp_login_http_flow() -> None:
    service, _store, _dispatcher, _denylist, _tokens, _clock_fn, _limiter = _auth()
    app = create_app()
    app.dependency_overrides[get_auth_service] = lambda: service
    app.dependency_overrides[get_file_service] = lambda: _NullFiles()
    client = TestClient(app)

    sent = client.post("/api/v1/auth/otp", json={"phone": "9876543210", "country_code": "+91"})
    assert sent.status_code == 200
    assert sent.json()["debug_code"]
    assert sent.headers["X-Request-ID"]

    verified = client.post(
        "/api/v1/auth/otp/verify",
        json={"phone": "9876543210", "country_code": "+91", "code": sent.json()["debug_code"]},
    )
    assert verified.status_code == 200
    body = verified.json()
    assert body["token_type"] == "bearer"
    assert body["is_new_user"] is True
    assert body["role"] == "member"
    assert body["profile"]["phone"] == "9876543210"
    assert body["profile"]["country_code"] == "+91"
    assert body["profile"]["profile_completed"] is False


def test_me_requires_access_token() -> None:
    client = TestClient(create_app())

    missing = client.get("/api/v1/me")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"

    invalid = client.get("/api/v1/me", headers={"Authorization": "Bearer not-a-token"})
    assert invalid.status_code == 401
    assert invalid.json()["error"]["code"] == "unauthorized"
