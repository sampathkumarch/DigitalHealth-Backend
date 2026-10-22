from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.diseases import SEARCH_LIMIT, Disease, DiseaseCategory, UserDiagnosis
from app.infrastructure.db.models import DiseaseCategoryModel, DiseaseModel, UserDiagnosisModel
from app.repositories.errors import DuplicateRecord


def _conflict(exc: IntegrityError) -> DuplicateRecord:
    text = str(getattr(exc, "orig", exc)).lower()
    if "code" in text:
        return DuplicateRecord("code")
    if "categor" in text:
        return DuplicateRecord("category")
    if "custom" in text:
        return DuplicateRecord("custom")
    return DuplicateRecord("disease")


def _flush(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError as exc:
        raise _conflict(exc) from exc


def _category(row: DiseaseCategoryModel) -> DiseaseCategory:
    return DiseaseCategory(
        id=row.id,
        name=row.name,
        description=row.description or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _disease(row: DiseaseModel, category_name: str | None) -> Disease:
    return Disease(
        id=row.id,
        name=row.name,
        code=row.code,
        code_system=row.code_system,
        category_id=row.category_id,
        description=row.description or "",
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
        category_name=category_name or "",
    )


def _diagnosis(row: UserDiagnosisModel, disease: DiseaseModel | None) -> UserDiagnosis:
    return UserDiagnosis(
        id=row.id,
        user_id=row.user_id,
        disease_id=row.disease_id,
        custom_disease_name=row.custom_disease_name,
        diagnosis_status=row.diagnosis_status,
        review_status=row.review_status,
        diagnosed_at=row.diagnosed_at,
        notes=row.notes or "",
        created_at=row.created_at,
        updated_at=row.updated_at,
        disease_name=disease.name if disease else None,
        disease_code=disease.code if disease else None,
        code_system=disease.code_system if disease else None,
    )


def _contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


class SqlDiseaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_categories(self) -> list[DiseaseCategory]:
        rows = self._session.scalars(select(DiseaseCategoryModel).order_by(DiseaseCategoryModel.name)).all()
        return [_category(row) for row in rows]

    def get_category(self, category_id: UUID) -> DiseaseCategory | None:
        row = self._session.get(DiseaseCategoryModel, category_id)
        if row is None:
            return None
        return _category(row)

    def add_category(self, category: DiseaseCategory) -> None:
        self._session.add(
            DiseaseCategoryModel(
                id=category.id,
                name=category.name,
                description=category.description or None,
                created_at=category.created_at,
                updated_at=category.updated_at,
            )
        )
        _flush(self._session)

    def save_category(self, category: DiseaseCategory) -> None:
        row = self._session.get(DiseaseCategoryModel, category.id)
        if row is None:
            return
        row.name = category.name
        row.description = category.description or None
        row.updated_at = category.updated_at
        _flush(self._session)

    def delete_category(self, category_id: UUID) -> bool:
        row = self._session.get(DiseaseCategoryModel, category_id)
        if row is None:
            return False
        diseases = self._session.scalars(
            select(DiseaseModel).where(DiseaseModel.category_id == category_id)
        ).all()
        for disease in diseases:
            disease.category_id = None
        self._session.delete(row)
        _flush(self._session)
        return True

    def get_disease(self, disease_id: UUID) -> Disease | None:
        row = self._session.execute(
            select(DiseaseModel, DiseaseCategoryModel.name)
            .outerjoin(DiseaseCategoryModel, DiseaseCategoryModel.id == DiseaseModel.category_id)
            .where(DiseaseModel.id == disease_id)
        ).one_or_none()
        if row is None:
            return None
        disease, category_name = row
        return _disease(disease, category_name)

    def search_diseases(
        self,
        *,
        query: str,
        category_id: UUID | None,
        include_inactive: bool,
    ) -> list[Disease]:
        stmt = select(DiseaseModel, DiseaseCategoryModel.name).outerjoin(
            DiseaseCategoryModel,
            DiseaseCategoryModel.id == DiseaseModel.category_id,
        )
        if not include_inactive:
            stmt = stmt.where(DiseaseModel.is_active.is_(True))
        if category_id is not None:
            stmt = stmt.where(DiseaseModel.category_id == category_id)
        if query:
            pattern = _contains(query)
            stmt = stmt.where(
                or_(
                    DiseaseModel.name.ilike(pattern, escape="\\"),
                    DiseaseModel.code.ilike(pattern, escape="\\"),
                )
            )
        stmt = stmt.order_by(DiseaseModel.name).limit(SEARCH_LIMIT)
        return [_disease(disease, category_name) for disease, category_name in self._session.execute(stmt).all()]

    def add_disease(self, disease: Disease) -> None:
        self._session.add(
            DiseaseModel(
                id=disease.id,
                name=disease.name,
                code=disease.code,
                code_system=disease.code_system,
                category_id=disease.category_id,
                description=disease.description or None,
                is_active=disease.is_active,
                created_at=disease.created_at,
                updated_at=disease.updated_at,
            )
        )
        _flush(self._session)

    def save_disease(self, disease: Disease) -> None:
        row = self._session.get(DiseaseModel, disease.id)
        if row is None:
            return
        row.name = disease.name
        row.code = disease.code
        row.code_system = disease.code_system
        row.category_id = disease.category_id
        row.description = disease.description or None
        row.is_active = disease.is_active
        row.updated_at = disease.updated_at
        _flush(self._session)


class SqlDiagnosisRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_for_user(self, user_id: UUID) -> list[UserDiagnosis]:
        rows = self._session.execute(
            select(UserDiagnosisModel, DiseaseModel)
            .outerjoin(DiseaseModel, DiseaseModel.id == UserDiagnosisModel.disease_id)
            .where(UserDiagnosisModel.user_id == user_id)
            .order_by(UserDiagnosisModel.created_at, UserDiagnosisModel.id)
        ).all()
        return [_diagnosis(diagnosis, disease) for diagnosis, disease in rows]

    def get(self, diagnosis_id: UUID) -> UserDiagnosis | None:
        row = self._session.execute(
            select(UserDiagnosisModel, DiseaseModel)
            .outerjoin(DiseaseModel, DiseaseModel.id == UserDiagnosisModel.disease_id)
            .where(UserDiagnosisModel.id == diagnosis_id)
        ).one_or_none()
        if row is None:
            return None
        diagnosis, disease = row
        return _diagnosis(diagnosis, disease)

    def add(self, diagnosis: UserDiagnosis) -> None:
        self._session.add(
            UserDiagnosisModel(
                id=diagnosis.id,
                user_id=diagnosis.user_id,
                disease_id=diagnosis.disease_id,
                custom_disease_name=diagnosis.custom_disease_name,
                diagnosis_status=diagnosis.diagnosis_status,
                review_status=diagnosis.review_status,
                diagnosed_at=diagnosis.diagnosed_at,
                notes=diagnosis.notes or None,
                created_at=diagnosis.created_at,
                updated_at=diagnosis.updated_at,
            )
        )
        _flush(self._session)

    def save(self, diagnosis: UserDiagnosis) -> None:
        row = self._session.get(UserDiagnosisModel, diagnosis.id)
        if row is None:
            return
        row.disease_id = diagnosis.disease_id
        row.custom_disease_name = diagnosis.custom_disease_name
        row.diagnosis_status = diagnosis.diagnosis_status
        row.review_status = diagnosis.review_status
        row.diagnosed_at = diagnosis.diagnosed_at
        row.notes = diagnosis.notes or None
        row.updated_at = diagnosis.updated_at
        _flush(self._session)

    def delete(self, diagnosis_id: UUID) -> None:
        row = self._session.get(UserDiagnosisModel, diagnosis_id)
        if row is None:
            return
        self._session.delete(row)
        _flush(self._session)

    def find_catalog_duplicate(self, user_id: UUID, disease_id: UUID) -> UserDiagnosis | None:
        row = self._session.scalar(
            select(UserDiagnosisModel).where(
                UserDiagnosisModel.user_id == user_id,
                UserDiagnosisModel.disease_id == disease_id,
            )
        )
        if row is None:
            return None
        return _diagnosis(row, None)

    def find_custom_duplicate(self, user_id: UUID, name: str) -> UserDiagnosis | None:
        row = self._session.scalar(
            select(UserDiagnosisModel).where(
                UserDiagnosisModel.user_id == user_id,
                func.lower(UserDiagnosisModel.custom_disease_name) == name.casefold(),
            )
        )
        if row is None:
            return None
        return _diagnosis(row, None)
