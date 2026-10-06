from fastapi.testclient import TestClient


def test_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "message" in response.json()
    assert response.headers["X-Request-ID"]


def test_health(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "req-1"})

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["X-Request-ID"] == "req-1"


def test_unknown_path_uses_error_envelope(client: TestClient) -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_error"
    assert body["error"]["request_id"]
