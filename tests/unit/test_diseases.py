from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.domain.users import new_member
from app.services.diagnoses import DiagnosisService
from app.services.diseases import DiseaseCatalogService
from tests.fakes import MemoryStore, MemoryUnitOfWorkFactory


def _services():
    store = MemoryStore()
    factory = MemoryUnitOfWorkFactory(store)
    return DiseaseCatalogService(factory), DiagnosisService(factory), store


def test_search_by_name_code_and_category() -> None:
    catalog, _diagnoses, _store = _services()
    heart = catalog.create_category(name="Cardiovascular", description="")
    hormone = catalog.create_category(name="Endocrine", description="")
    catalog.create_disease(
        name="Hypertension",
        code=None,
        code_system=None,
        category_id=heart.id,
        description="",
        is_active=True,
    )
    diabetes = catalog.create_disease(
        name="Diabetes",
        code="E11",
        code_system="ICD-10",
        category_id=hormone.id,
        description="",
        is_active=True,
    )

    by_name = catalog.search(query="hyper", category_id=None, include_inactive=False)
    assert [item.name for item in by_name] == ["Hypertension"]

    by_code = catalog.search(query="e11", category_id=None, include_inactive=False)
    assert [item.id for item in by_code] == [diabetes.id]
    assert by_code[0].category_name == "Endocrine"

    filtered = catalog.search(query="", category_id=hormone.id, include_inactive=False)
    assert [item.name for item in filtered] == ["Diabetes"]


def test_inactive_disease_is_hidden_and_cannot_be_selected() -> None:
    catalog, diagnoses, _store = _services()
    created = catalog.create_disease(
        name="Asthma",
        code=None,
        code_system=None,
        category_id=None,
        description="",
        is_active=True,
    )
    catalog.deactivate_disease(created.id)
    assert catalog.search(query="asth", category_id=None, include_inactive=False) == []
    hidden = catalog.search(query="asth", category_id=None, include_inactive=True)
    assert hidden[0].is_active is False

    user = new_member("+91", "9876543210", created.created_at)
    with pytest.raises(NotFoundError):
        diagnoses.add(
            user.id,
            disease_id=created.id,
            custom_disease_name=None,
            diagnosed_at=None,
            notes="",
        )


def test_multiple_catalog_and_custom_selections() -> None:
    catalog, diagnoses, store = _services()
    heart = catalog.create_category(name="Cardiovascular", description="")
    diabetes = catalog.create_disease(
        name="Diabetes",
        code=None,
        code_system=None,
        category_id=None,
        description="",
        is_active=True,
    )
    pressure = catalog.create_disease(
        name="Hypertension",
        code=None,
        code_system=None,
        category_id=heart.id,
        description="",
        is_active=True,
    )
    user = new_member("+91", "9876543210", diabetes.created_at)
    saved = diagnoses.replace(
        user.id,
        [
            (diabetes.id, None),
            (pressure.id, None),
            (None, "Migraine"),
        ],
    )

    by_name = {item.display_name: item for item in saved}
    assert set(by_name) == {"Diabetes", "Hypertension", "Migraine"}
    assert by_name["Diabetes"].review_status == "confirmed"
    assert by_name["Hypertension"].review_status == "confirmed"
    assert by_name["Migraine"].review_status == "unverified"
    assert by_name["Migraine"].disease_id is None
    assert not hasattr(by_name["Diabetes"], "category_id")
    assert len(store.diseases) == 2

    with pytest.raises(ConflictError):
        diagnoses.add(
            user.id,
            disease_id=diabetes.id,
            custom_disease_name=None,
            diagnosed_at=None,
            notes="",
        )
    with pytest.raises(ConflictError):
        diagnoses.add(
            user.id,
            disease_id=None,
            custom_disease_name="migraine",
            diagnosed_at=None,
            notes="",
        )

    trimmed = diagnoses.replace(user.id, [(diabetes.id, None), (None, "Migraine")])
    assert {item.display_name for item in trimmed} == {"Diabetes", "Migraine"}


def test_custom_entry_can_be_mapped_without_losing_the_typed_name() -> None:
    catalog, diagnoses, store = _services()
    diabetes = catalog.create_disease(
        name="Diabetes",
        code=None,
        code_system=None,
        category_id=None,
        description="",
        is_active=True,
    )
    user = new_member("+91", "9876543210", diabetes.created_at)
    custom = diagnoses.add(
        user.id,
        disease_id=None,
        custom_disease_name="Sugar",
        diagnosed_at=None,
        notes="",
    )
    assert custom.review_status == "unverified"
    assert len(store.diseases) == 1

    mapped = diagnoses.map_to_catalog(user.id, custom.id, diabetes.id)
    assert mapped.review_status == "mapped"
    assert mapped.disease_id == diabetes.id
    assert mapped.custom_disease_name == "Sugar"
    assert mapped.display_name == "Diabetes"
    assert len(store.diseases) == 1


def test_selection_must_be_a_catalog_disease_or_a_typed_name() -> None:
    _catalog, diagnoses, _store = _services()
    user_id = uuid4()
    with pytest.raises(ValidationFailed):
        diagnoses.add(
            user_id,
            disease_id=None,
            custom_disease_name="  ",
            diagnosed_at=None,
            notes="",
        )
    with pytest.raises(ValidationFailed):
        diagnoses.add(
            user_id,
            disease_id=uuid4(),
            custom_disease_name="Migraine",
            diagnosed_at=None,
            notes="",
        )


def test_code_requires_a_coding_system_and_future_date_is_rejected() -> None:
    catalog, diagnoses, _store = _services()
    with pytest.raises(ValidationFailed):
        catalog.create_disease(
            name="Diabetes",
            code="E11",
            code_system=None,
            category_id=None,
            description="",
            is_active=True,
        )
    disease = catalog.create_disease(
        name="Diabetes",
        code=None,
        code_system=None,
        category_id=None,
        description="",
        is_active=True,
    )
    with pytest.raises(ValidationFailed):
        diagnoses.add(
            uuid4(),
            disease_id=disease.id,
            custom_disease_name=None,
            diagnosed_at=date.today() + timedelta(days=1),
            notes="",
        )


def test_duplicate_category_name_is_rejected() -> None:
    catalog, _diagnoses, _store = _services()
    catalog.create_category(name="Endocrine", description="")
    with pytest.raises(ConflictError):
        catalog.create_category(name="endocrine", description="")
