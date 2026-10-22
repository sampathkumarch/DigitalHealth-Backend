from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_admin_user, get_current_user, get_disease_service
from app.core.exceptions import ForbiddenError
from app.domain.roles import ADMIN
from app.domain.users import UserAccount
from app.schemas.diseases import (
    CategoryResponse,
    CategoryWriteRequest,
    DiseaseResponse,
    DiseaseWriteRequest,
    category_response,
    disease_response,
)
from app.services.diseases import DiseaseCatalogService

categories = APIRouter(prefix="/disease-categories", tags=["disease-categories"])
diseases = APIRouter(prefix="/diseases", tags=["diseases"])


@categories.get("", response_model=list[CategoryResponse])
def list_categories(
    _user: UserAccount = Depends(get_current_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> list[CategoryResponse]:
    return [category_response(item) for item in service.list_categories()]


@categories.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryWriteRequest,
    _admin: UserAccount = Depends(get_admin_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> CategoryResponse:
    category = service.create_category(name=body.name, description=body.description)
    return category_response(category)


@categories.put("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: UUID,
    body: CategoryWriteRequest,
    _admin: UserAccount = Depends(get_admin_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> CategoryResponse:
    category = service.update_category(category_id, name=body.name, description=body.description)
    return category_response(category)


@categories.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    _admin: UserAccount = Depends(get_admin_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> None:
    service.delete_category(category_id)


@diseases.get("", response_model=list[DiseaseResponse])
def search_diseases(
    q: str = "",
    category_id: UUID | None = None,
    include_inactive: bool = False,
    user: UserAccount = Depends(get_current_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> list[DiseaseResponse]:
    if include_inactive and user.role != ADMIN:
        raise ForbiddenError("Admin access is required.")
    found = service.search(query=q, category_id=category_id, include_inactive=include_inactive)
    return [disease_response(item) for item in found]


@diseases.get("/{disease_id}", response_model=DiseaseResponse)
def read_disease(
    disease_id: UUID,
    user: UserAccount = Depends(get_current_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> DiseaseResponse:
    disease = service.get_disease(disease_id, include_inactive=user.role == ADMIN)
    return disease_response(disease)


@diseases.post("", response_model=DiseaseResponse, status_code=status.HTTP_201_CREATED)
def create_disease(
    body: DiseaseWriteRequest,
    _admin: UserAccount = Depends(get_admin_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> DiseaseResponse:
    disease = service.create_disease(
        name=body.name,
        code=body.code,
        code_system=body.code_system,
        category_id=body.category_id,
        description=body.description,
        is_active=body.is_active,
    )
    return disease_response(disease)


@diseases.put("/{disease_id}", response_model=DiseaseResponse)
def update_disease(
    disease_id: UUID,
    body: DiseaseWriteRequest,
    _admin: UserAccount = Depends(get_admin_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> DiseaseResponse:
    disease = service.update_disease(
        disease_id,
        name=body.name,
        code=body.code,
        code_system=body.code_system,
        category_id=body.category_id,
        description=body.description,
        is_active=body.is_active,
    )
    return disease_response(disease)


@diseases.delete("/{disease_id}", response_model=DiseaseResponse)
def deactivate_disease(
    disease_id: UUID,
    _admin: UserAccount = Depends(get_admin_user),
    service: DiseaseCatalogService = Depends(get_disease_service),
) -> DiseaseResponse:
    return disease_response(service.deactivate_disease(disease_id))
