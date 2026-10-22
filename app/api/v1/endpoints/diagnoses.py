from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_diagnosis_service
from app.domain.users import UserAccount
from app.schemas.diseases import (
    DiagnosisCreateRequest,
    DiagnosisResponse,
    MapDiagnosisRequest,
    ReplaceDiagnosesRequest,
    diagnosis_response,
)
from app.services.diagnoses import DiagnosisService

router = APIRouter(prefix="/me/diagnoses", tags=["diagnoses"])


@router.get("", response_model=list[DiagnosisResponse])
def list_diagnoses(
    user: UserAccount = Depends(get_current_user),
    service: DiagnosisService = Depends(get_diagnosis_service),
) -> list[DiagnosisResponse]:
    return [diagnosis_response(item) for item in service.list_for_user(user.id)]


@router.put("", response_model=list[DiagnosisResponse])
def replace_diagnoses(
    body: ReplaceDiagnosesRequest,
    user: UserAccount = Depends(get_current_user),
    service: DiagnosisService = Depends(get_diagnosis_service),
) -> list[DiagnosisResponse]:
    items = [(item.disease_id, item.custom_disease_name) for item in body.selections]
    return [diagnosis_response(item) for item in service.replace(user.id, items)]


@router.post("", response_model=DiagnosisResponse, status_code=status.HTTP_201_CREATED)
def add_diagnosis(
    body: DiagnosisCreateRequest,
    user: UserAccount = Depends(get_current_user),
    service: DiagnosisService = Depends(get_diagnosis_service),
) -> DiagnosisResponse:
    diagnosis = service.add(
        user.id,
        disease_id=body.disease_id,
        custom_disease_name=body.custom_disease_name,
        diagnosed_at=body.diagnosed_at,
        notes=body.notes,
    )
    return diagnosis_response(diagnosis)


@router.post("/{diagnosis_id}/map", response_model=DiagnosisResponse)
def map_diagnosis(
    diagnosis_id: UUID,
    body: MapDiagnosisRequest,
    user: UserAccount = Depends(get_current_user),
    service: DiagnosisService = Depends(get_diagnosis_service),
) -> DiagnosisResponse:
    diagnosis = service.map_to_catalog(user.id, diagnosis_id, body.disease_id)
    return diagnosis_response(diagnosis)


@router.delete("/{diagnosis_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_diagnosis(
    diagnosis_id: UUID,
    user: UserAccount = Depends(get_current_user),
    service: DiagnosisService = Depends(get_diagnosis_service),
) -> None:
    service.remove(user.id, diagnosis_id)
