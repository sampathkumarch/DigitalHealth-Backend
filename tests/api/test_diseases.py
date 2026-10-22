from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_diagnosis_service, get_disease_service
from app.domain.users import new_member
from app.main import create_app
from app.services.diagnoses import DiagnosisService
from app.services.diseases import DiseaseCatalogService
from tests.fakes import MemoryStore, MemoryUnitOfWorkFactory


def test_disease_routes_require_a_signed_in_user() -> None:
    client = TestClient(create_app())

    missing = client.get("/api/v1/diseases")
    assert missing.status_code == 401
    assert missing.json()["error"]["code"] == "unauthorized"


def test_member_cannot_change_the_catalog() -> None:
    app = create_app()
    member = new_member("+91", "9876543210", datetime.now(timezone.utc))
    app.dependency_overrides[get_current_user] = lambda: member
    client = TestClient(app)

    response = client.post("/api/v1/diseases", json={"name": "Diabetes"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_member_can_search_and_save_several_diagnoses() -> None:
    store = MemoryStore()
    factory = MemoryUnitOfWorkFactory(store)
    catalog = DiseaseCatalogService(factory)
    diagnoses = DiagnosisService(factory)
    category = catalog.create_category(name="Endocrine", description="")
    disease = catalog.create_disease(
        name="Diabetes",
        code=None,
        code_system=None,
        category_id=category.id,
        description="",
        is_active=True,
    )
    member = new_member("+91", "9876543210", disease.created_at)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: member
    app.dependency_overrides[get_disease_service] = lambda: catalog
    app.dependency_overrides[get_diagnosis_service] = lambda: diagnoses
    client = TestClient(app)

    found = client.get("/api/v1/diseases", params={"q": "dia", "category_id": str(category.id)})
    assert found.status_code == 200
    assert found.json()[0]["name"] == "Diabetes"
    assert found.json()[0]["category_name"] == "Endocrine"

    saved = client.put(
        "/api/v1/me/diagnoses",
        json={
            "selections": [
                {"disease_id": str(disease.id)},
                {"custom_disease_name": "Migraine"},
            ]
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    by_name = {item["display_name"]: item for item in body}
    assert set(by_name) == {"Diabetes", "Migraine"}
    assert by_name["Diabetes"]["review_status"] == "confirmed"
    assert by_name["Migraine"]["review_status"] == "unverified"
    assert by_name["Migraine"]["disease_id"] is None
    assert len(store.diseases) == 1
