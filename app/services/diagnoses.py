from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.domain.diseases import (
    ACTIVE,
    CONFIRMED,
    MAPPED,
    UNVERIFIED,
    CatalogSelection,
    CustomSelection,
    Disease,
    Selection,
    UserDiagnosis,
    clean_diagnosed_at,
    clean_notes,
    parse_selection,
    parse_selections,
)
from app.domain.errors import DomainError
from app.repositories.errors import DuplicateRecord
from app.repositories.unit_of_work import UnitOfWorkFactory


class DiagnosisService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock=None) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def list_for_user(self, user_id: UUID) -> list[UserDiagnosis]:
        with self._uow_factory() as uow:
            return uow.diagnoses.list_for_user(user_id)

    def add(
        self,
        user_id: UUID,
        *,
        disease_id: UUID | None,
        custom_disease_name: str | None,
        diagnosed_at,
        notes: str,
    ) -> UserDiagnosis:
        selection = _one(disease_id, custom_disease_name)
        when, cleaned_notes = _extras(diagnosed_at, notes, self._clock().date())
        now = self._clock()
        with self._uow_factory() as uow:
            disease = self._catalog_disease(uow, selection)
            self._reject_duplicate(uow, user_id, selection)
            diagnosis = UserDiagnosis(
                id=uuid4(),
                user_id=user_id,
                disease_id=disease.id if disease else None,
                custom_disease_name=selection.name if isinstance(selection, CustomSelection) else None,
                diagnosis_status=ACTIVE,
                review_status=CONFIRMED if disease else UNVERIFIED,
                diagnosed_at=when,
                notes=cleaned_notes,
                created_at=now,
                updated_at=now,
                disease_name=disease.name if disease else None,
                disease_code=disease.code if disease else None,
                code_system=disease.code_system if disease else None,
            )
            try:
                uow.diagnoses.add(diagnosis)
                uow.commit()
            except DuplicateRecord as exc:
                raise _duplicate(exc) from exc
            return uow.diagnoses.get(diagnosis.id) or diagnosis

    def replace(self, user_id: UUID, items: list[tuple[UUID | None, str | None]]) -> list[UserDiagnosis]:
        selections = _many(items)
        with self._uow_factory() as uow:
            diseases = {
                selection.disease_id: self._catalog_disease(uow, selection)
                for selection in selections
                if isinstance(selection, CatalogSelection)
            }
            existing = uow.diagnoses.list_for_user(user_id)
            kept: list[UserDiagnosis] = []
            used: set[UUID] = set()
            pending: list[Selection] = []
            for selection in selections:
                if any(_matches(row, selection) for row in kept):
                    continue
                match = next(
                    (row for row in existing if row.id not in used and _matches(row, selection)),
                    None,
                )
                if match is None:
                    pending.append(selection)
                    continue
                used.add(match.id)
                kept.append(match)
            for row in existing:
                if row.id not in used:
                    uow.diagnoses.delete(row.id)
            now = self._clock()
            for selection in pending:
                disease = diseases.get(selection.disease_id) if isinstance(selection, CatalogSelection) else None
                uow.diagnoses.add(
                    UserDiagnosis(
                        id=uuid4(),
                        user_id=user_id,
                        disease_id=disease.id if disease else None,
                        custom_disease_name=selection.name if isinstance(selection, CustomSelection) else None,
                        diagnosis_status=ACTIVE,
                        review_status=CONFIRMED if disease else UNVERIFIED,
                        diagnosed_at=None,
                        notes="",
                        created_at=now,
                        updated_at=now,
                    )
                )
            try:
                uow.commit()
            except DuplicateRecord as exc:
                raise _duplicate(exc) from exc
            return uow.diagnoses.list_for_user(user_id)

    def remove(self, user_id: UUID, diagnosis_id: UUID) -> None:
        with self._uow_factory() as uow:
            diagnosis = self._owned(uow, user_id, diagnosis_id)
            uow.diagnoses.delete(diagnosis.id)
            uow.commit()

    def map_to_catalog(self, user_id: UUID, diagnosis_id: UUID, disease_id: UUID) -> UserDiagnosis:
        with self._uow_factory() as uow:
            diagnosis = self._owned(uow, user_id, diagnosis_id)
            if not diagnosis.custom_disease_name:
                raise ValidationFailed(
                    "Only a typed diagnosis can be linked to the catalog.",
                    {"disease_id": "Only a typed diagnosis can be linked to the catalog."},
                )
            disease = uow.diseases.get_disease(disease_id)
            if disease is None or not disease.is_active:
                raise NotFoundError("Disease not found")
            other = uow.diagnoses.find_catalog_duplicate(user_id, disease.id)
            if other is not None and other.id != diagnosis.id:
                raise ConflictError("That disease is already on your list.")
            diagnosis.disease_id = disease.id
            diagnosis.review_status = MAPPED
            diagnosis.updated_at = self._clock()
            diagnosis.disease_name = disease.name
            diagnosis.disease_code = disease.code
            diagnosis.code_system = disease.code_system
            try:
                uow.diagnoses.save(diagnosis)
                uow.commit()
            except DuplicateRecord as exc:
                raise _duplicate(exc) from exc
            return uow.diagnoses.get(diagnosis.id) or diagnosis

    def _catalog_disease(self, uow, selection: Selection) -> Disease | None:
        if isinstance(selection, CustomSelection):
            return None
        disease = uow.diseases.get_disease(selection.disease_id)
        if disease is None or not disease.is_active:
            raise NotFoundError("Disease not found")
        return disease

    def _reject_duplicate(self, uow, user_id: UUID, selection: Selection) -> None:
        if isinstance(selection, CatalogSelection):
            if uow.diagnoses.find_catalog_duplicate(user_id, selection.disease_id) is not None:
                raise ConflictError("That disease is already on your list.")
            return
        if uow.diagnoses.find_custom_duplicate(user_id, selection.name) is not None:
            raise ConflictError("That name is already on your list.")

    def _owned(self, uow, user_id: UUID, diagnosis_id: UUID) -> UserDiagnosis:
        diagnosis = uow.diagnoses.get(diagnosis_id)
        if diagnosis is None or diagnosis.user_id != user_id:
            raise NotFoundError("Diagnosis not found")
        return diagnosis


def _one(disease_id: UUID | None, custom_name: str | None) -> Selection:
    try:
        return parse_selection(disease_id, custom_name)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc


def _many(items: list[tuple[UUID | None, str | None]]) -> list[Selection]:
    try:
        return parse_selections(items)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc


def _extras(diagnosed_at, notes: str, today):
    try:
        return clean_diagnosed_at(diagnosed_at, today), clean_notes(notes)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc


def _matches(row: UserDiagnosis, selection: Selection) -> bool:
    if isinstance(selection, CatalogSelection):
        return row.disease_id == selection.disease_id
    if row.custom_disease_name is None:
        return False
    return row.custom_disease_name.casefold() == selection.name.casefold()


def _duplicate(exc: DuplicateRecord) -> ConflictError:
    if exc.field == "custom":
        return ConflictError("That name is already on your list.")
    return ConflictError("That disease is already on your list.")
