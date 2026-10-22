from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.diseases import Disease, DiseaseCategory, UserDiagnosis


class CategoryWriteRequest(BaseModel):
    name: str
    description: str = ""


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class DiseaseWriteRequest(BaseModel):
    name: str
    code: str | None = None
    code_system: str | None = None
    category_id: UUID | None = None
    description: str = ""
    is_active: bool = True


class DiseaseResponse(BaseModel):
    id: UUID
    name: str
    code: str | None
    code_system: str | None
    category_id: UUID | None
    category_name: str
    description: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DiagnosisCreateRequest(BaseModel):
    disease_id: UUID | None = None
    custom_disease_name: str | None = None
    diagnosed_at: date | None = None
    notes: str = ""


class SelectionItem(BaseModel):
    disease_id: UUID | None = None
    custom_disease_name: str | None = None


class ReplaceDiagnosesRequest(BaseModel):
    selections: list[SelectionItem]


class MapDiagnosisRequest(BaseModel):
    disease_id: UUID


class DiagnosisResponse(BaseModel):
    id: UUID
    disease_id: UUID | None
    disease_name: str | None
    disease_code: str | None
    code_system: str | None
    custom_disease_name: str | None
    display_name: str
    diagnosis_status: str
    review_status: str
    diagnosed_at: date | None
    notes: str
    created_at: datetime
    updated_at: datetime


def category_response(category: DiseaseCategory) -> CategoryResponse:
    return CategoryResponse(
        id=category.id,
        name=category.name,
        description=category.description,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def disease_response(disease: Disease) -> DiseaseResponse:
    return DiseaseResponse(
        id=disease.id,
        name=disease.name,
        code=disease.code,
        code_system=disease.code_system,
        category_id=disease.category_id,
        category_name=disease.category_name,
        description=disease.description,
        is_active=disease.is_active,
        created_at=disease.created_at,
        updated_at=disease.updated_at,
    )


def diagnosis_response(diagnosis: UserDiagnosis) -> DiagnosisResponse:
    return DiagnosisResponse(
        id=diagnosis.id,
        disease_id=diagnosis.disease_id,
        disease_name=diagnosis.disease_name,
        disease_code=diagnosis.disease_code,
        code_system=diagnosis.code_system,
        custom_disease_name=diagnosis.custom_disease_name,
        display_name=diagnosis.display_name,
        diagnosis_status=diagnosis.diagnosis_status,
        review_status=diagnosis.review_status,
        diagnosed_at=diagnosis.diagnosed_at,
        notes=diagnosis.notes,
        created_at=diagnosis.created_at,
        updated_at=diagnosis.updated_at,
    )
