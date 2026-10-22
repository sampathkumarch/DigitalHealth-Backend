from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from app.domain.errors import DomainError

CONFIRMED = "confirmed"
UNVERIFIED = "unverified"
MAPPED = "mapped"
ACTIVE = "active"

NAME_MAX = 200
CATEGORY_NAME_MAX = 120
CODE_MAX = 32
CODE_SYSTEM_MAX = 64
DESCRIPTION_MAX = 1000
NOTES_MAX = 2000
SEARCH_LIMIT = 50


@dataclass
class DiseaseCategory:
    id: UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


@dataclass
class Disease:
    id: UUID
    name: str
    code: str | None
    code_system: str | None
    category_id: UUID | None
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    category_name: str = ""


@dataclass
class UserDiagnosis:
    id: UUID
    user_id: UUID
    disease_id: UUID | None
    custom_disease_name: str | None
    diagnosis_status: str
    review_status: str
    diagnosed_at: date | None
    notes: str
    created_at: datetime
    updated_at: datetime
    disease_name: str | None = None
    disease_code: str | None = None
    code_system: str | None = None

    @property
    def display_name(self) -> str:
        if self.review_status == UNVERIFIED or not self.disease_name:
            return self.custom_disease_name or self.disease_name or ""
        return self.disease_name


@dataclass(frozen=True)
class CatalogSelection:
    disease_id: UUID


@dataclass(frozen=True)
class CustomSelection:
    name: str


Selection = CatalogSelection | CustomSelection


def clean_category_name(name: str) -> str:
    return _required(name, field="name", label="category name", limit=CATEGORY_NAME_MAX)


def clean_description(description: str) -> str:
    text = description.strip()
    if len(text) > DESCRIPTION_MAX:
        raise DomainError(
            "Keep the description under 1000 characters.",
            {"description": "Keep the description under 1000 characters."},
        )
    return text


def clean_disease_name(name: str) -> str:
    return _required(name, field="name", label="disease name", limit=NAME_MAX)


def clean_code(code: str | None, code_system: str | None) -> tuple[str | None, str | None]:
    cleaned_code = (code or "").strip()
    cleaned_system = (code_system or "").strip()
    if not cleaned_code and not cleaned_system:
        return None, None
    if not cleaned_code or not cleaned_system:
        message = "Enter both a code and its coding system, or leave both empty."
        raise DomainError(message, {"code": message})
    if len(cleaned_code) > CODE_MAX:
        raise DomainError(
            "Keep the code under 32 characters.",
            {"code": "Keep the code under 32 characters."},
        )
    if len(cleaned_system) > CODE_SYSTEM_MAX:
        raise DomainError(
            "Keep the coding system under 64 characters.",
            {"code_system": "Keep the coding system under 64 characters."},
        )
    return cleaned_code, cleaned_system


def clean_notes(notes: str) -> str:
    text = notes.strip()
    if len(text) > NOTES_MAX:
        raise DomainError(
            "Keep notes under 2000 characters.",
            {"notes": "Keep notes under 2000 characters."},
        )
    return text


def clean_diagnosed_at(value: date | None, today: date) -> date | None:
    if value is None:
        return None
    if value > today:
        raise DomainError(
            "Diagnosis date cannot be in the future.",
            {"diagnosed_at": "Diagnosis date cannot be in the future."},
        )
    return value


def parse_selection(disease_id: UUID | None, custom_name: str | None) -> Selection:
    name = (custom_name or "").strip()
    has_id = disease_id is not None
    has_name = bool(name)
    if has_id and has_name:
        message = "Choose a listed disease or enter a name, not both."
        raise DomainError(message, {"custom_disease_name": message})
    if not has_id and not has_name:
        message = "Choose a listed disease or enter a name."
        raise DomainError(message, {"custom_disease_name": message})
    if has_name:
        if len(name) > NAME_MAX:
            raise DomainError(
                "Keep the disease name under 200 characters.",
                {"custom_disease_name": "Keep the disease name under 200 characters."},
            )
        return CustomSelection(name)
    assert disease_id is not None
    return CatalogSelection(disease_id)


def parse_selections(
    items: list[tuple[UUID | None, str | None]],
) -> list[Selection]:
    parsed: list[Selection] = []
    seen_ids: set[UUID] = set()
    seen_names: set[str] = set()
    for disease_id, custom_name in items:
        selection = parse_selection(disease_id, custom_name)
        if isinstance(selection, CatalogSelection):
            if selection.disease_id in seen_ids:
                raise DomainError(
                    "That disease is already selected.",
                    {"disease_id": "That disease is already selected."},
                )
            seen_ids.add(selection.disease_id)
        else:
            key = selection.name.casefold()
            if key in seen_names:
                raise DomainError(
                    "That name is already selected.",
                    {"custom_disease_name": "That name is already selected."},
                )
            seen_names.add(key)
        parsed.append(selection)
    return parsed


def _required(value: str, *, field: str, label: str, limit: int) -> str:
    text = value.strip()
    if not text:
        message = f"Enter a {label}."
        raise DomainError(message, {field: message})
    if len(text) > limit:
        message = f"Keep the {label} under {limit} characters."
        raise DomainError(message, {field: message})
    return text
