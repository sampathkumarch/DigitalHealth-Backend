from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.domain.diseases import (
    SEARCH_LIMIT,
    Disease,
    DiseaseCategory,
    clean_category_name,
    clean_code,
    clean_description,
    clean_disease_name,
)
from app.domain.errors import DomainError
from app.repositories.errors import DuplicateRecord
from app.repositories.unit_of_work import UnitOfWorkFactory


class DiseaseCatalogService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock=None) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_categories(self) -> list[DiseaseCategory]:
        with self._uow_factory() as uow:
            return uow.diseases.list_categories()

    def create_category(self, *, name: str, description: str) -> DiseaseCategory:
        cleaned_name, cleaned_description = _category_fields(name, description)
        now = self._clock()
        category = DiseaseCategory(
            id=uuid4(),
            name=cleaned_name,
            description=cleaned_description,
            created_at=now,
            updated_at=now,
        )
        with self._uow_factory() as uow:
            self._require_unique_category(uow, cleaned_name, None)
            try:
                uow.diseases.add_category(category)
                uow.commit()
            except DuplicateRecord as exc:
                raise _category_conflict() from exc
            return category

    def update_category(
        self,
        category_id: UUID,
        *,
        name: str,
        description: str,
    ) -> DiseaseCategory:
        cleaned_name, cleaned_description = _category_fields(name, description)
        with self._uow_factory() as uow:
            category = uow.diseases.get_category(category_id)
            if category is None:
                raise NotFoundError("Category not found")
            self._require_unique_category(uow, cleaned_name, category_id)
            category.name = cleaned_name
            category.description = cleaned_description
            category.updated_at = self._clock()
            try:
                uow.diseases.save_category(category)
                uow.commit()
            except DuplicateRecord as exc:
                raise _category_conflict() from exc
            return category

    def delete_category(self, category_id: UUID) -> None:
        with self._uow_factory() as uow:
            if not uow.diseases.delete_category(category_id):
                raise NotFoundError("Category not found")
            uow.commit()

    def search(
        self,
        *,
        query: str,
        category_id: UUID | None,
        include_inactive: bool,
    ) -> list[Disease]:
        with self._uow_factory() as uow:
            if category_id is not None and uow.diseases.get_category(category_id) is None:
                raise NotFoundError("Category not found")
            return uow.diseases.search_diseases(
                query=query.strip(),
                category_id=category_id,
                include_inactive=include_inactive,
            )[:SEARCH_LIMIT]

    def get_disease(self, disease_id: UUID, *, include_inactive: bool) -> Disease:
        with self._uow_factory() as uow:
            disease = uow.diseases.get_disease(disease_id)
            if disease is None or (not disease.is_active and not include_inactive):
                raise NotFoundError("Disease not found")
            return disease

    def create_disease(
        self,
        *,
        name: str,
        code: str | None,
        code_system: str | None,
        category_id: UUID | None,
        description: str,
        is_active: bool,
    ) -> Disease:
        cleaned = _disease_fields(name, code, code_system, description)
        now = self._clock()
        disease = Disease(
            id=uuid4(),
            name=cleaned[0],
            code=cleaned[1],
            code_system=cleaned[2],
            category_id=category_id,
            description=cleaned[3],
            is_active=is_active,
            created_at=now,
            updated_at=now,
        )
        with self._uow_factory() as uow:
            self._require_category(uow, category_id)
            try:
                uow.diseases.add_disease(disease)
                uow.commit()
            except DuplicateRecord as exc:
                raise _code_conflict() from exc
            stored = uow.diseases.get_disease(disease.id)
            return stored or disease

    def update_disease(
        self,
        disease_id: UUID,
        *,
        name: str,
        code: str | None,
        code_system: str | None,
        category_id: UUID | None,
        description: str,
        is_active: bool,
    ) -> Disease:
        cleaned = _disease_fields(name, code, code_system, description)
        with self._uow_factory() as uow:
            disease = uow.diseases.get_disease(disease_id)
            if disease is None:
                raise NotFoundError("Disease not found")
            self._require_category(uow, category_id)
            disease.name = cleaned[0]
            disease.code = cleaned[1]
            disease.code_system = cleaned[2]
            disease.category_id = category_id
            disease.description = cleaned[3]
            disease.is_active = is_active
            disease.updated_at = self._clock()
            try:
                uow.diseases.save_disease(disease)
                uow.commit()
            except DuplicateRecord as exc:
                raise _code_conflict() from exc
            stored = uow.diseases.get_disease(disease.id)
            return stored or disease

    def deactivate_disease(self, disease_id: UUID) -> Disease:
        with self._uow_factory() as uow:
            disease = uow.diseases.get_disease(disease_id)
            if disease is None:
                raise NotFoundError("Disease not found")
            disease.is_active = False
            disease.updated_at = self._clock()
            uow.diseases.save_disease(disease)
            uow.commit()
            return disease

    def _require_category(self, uow, category_id: UUID | None) -> None:
        if category_id is None:
            return
        if uow.diseases.get_category(category_id) is None:
            raise ValidationFailed(
                "Choose a valid category.",
                {"category_id": "Choose a valid category."},
            )

    def _require_unique_category(self, uow, name: str, current_id: UUID | None) -> None:
        for category in uow.diseases.list_categories():
            if category.id != current_id and category.name.casefold() == name.casefold():
                raise _category_conflict()


def _category_fields(name: str, description: str) -> tuple[str, str]:
    try:
        return clean_category_name(name), clean_description(description)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc


def _disease_fields(
    name: str,
    code: str | None,
    code_system: str | None,
    description: str,
) -> tuple[str, str | None, str | None, str]:
    try:
        cleaned_name = clean_disease_name(name)
        cleaned_code, cleaned_system = clean_code(code, code_system)
        cleaned_description = clean_description(description)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc
    return cleaned_name, cleaned_code, cleaned_system, cleaned_description


def _category_conflict() -> ConflictError:
    return ConflictError("That category name is already used.")


def _code_conflict() -> ConflictError:
    return ConflictError("That code is already used for this coding system.")
