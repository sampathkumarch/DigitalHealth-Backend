import pytest

from app.domain.errors import DomainError
from app.domain.profile import ProfileSubmission, validate_profile


def _submit(**overrides: object) -> ProfileSubmission:
    payload = {
        "full_name": "Rahul Sharma",
        "email": "rahul@example.com",
        "date_of_birth": "12/05/1998",
        "weight_kg": "72.5",
        "blood_group": "O+",
        "conditions": ("Diabetes", "Other"),
        "other_condition": "Migraine",
    }
    payload.update(overrides)
    return ProfileSubmission(**payload)  # type: ignore[arg-type]


def test_profile_matches_frontend_rules() -> None:
    cleaned = validate_profile(_submit(), require_email_field=True)

    assert cleaned.full_name == "Rahul Sharma"
    assert cleaned.email == "rahul@example.com"
    assert cleaned.date_of_birth is not None
    assert cleaned.date_of_birth.isoformat() == "1998-05-12"
    assert str(cleaned.weight_kg) == "72.5"
    assert cleaned.blood_group == "O+"
    assert cleaned.conditions == ("Diabetes", "Other")
    assert cleaned.other_condition == "Migraine"


def test_register_requires_name_and_email() -> None:
    with pytest.raises(DomainError) as caught:
        validate_profile(_submit(full_name="  ", email=""), require_email_field=True)
    assert "full_name" in caught.value.fields
    assert "email" in caught.value.fields


def test_edit_allows_empty_email() -> None:
    cleaned = validate_profile(_submit(email=""), require_email_field=False)
    assert cleaned.email is None


def test_health_field_rules() -> None:
    with pytest.raises(DomainError) as weight:
        validate_profile(_submit(weight_kg="501"), require_email_field=False)
    assert "weight" in weight.value.fields

    with pytest.raises(DomainError) as blood:
        validate_profile(_submit(blood_group="Z+"), require_email_field=False)
    assert "blood_group" in blood.value.fields

    with pytest.raises(DomainError) as exclusive:
        validate_profile(
            _submit(conditions=("None", "Diabetes"), other_condition=""),
            require_email_field=False,
        )
    assert "conditions" in exclusive.value.fields

    with pytest.raises(DomainError) as other:
        validate_profile(
            _submit(conditions=("Other",), other_condition="  "),
            require_email_field=False,
        )
    assert "other_condition" in other.value.fields

    with pytest.raises(DomainError) as dob:
        validate_profile(_submit(date_of_birth="31/02/1998"), require_email_field=False)
    assert "date_of_birth" in dob.value.fields
