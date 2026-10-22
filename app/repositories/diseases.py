from typing import Protocol
from uuid import UUID

from app.domain.diseases import Disease, DiseaseCategory


class DiseaseRepository(Protocol):
    def list_categories(self) -> list[DiseaseCategory]: ...

    def get_category(self, category_id: UUID) -> DiseaseCategory | None: ...

    def add_category(self, category: DiseaseCategory) -> None: ...

    def save_category(self, category: DiseaseCategory) -> None: ...

    def delete_category(self, category_id: UUID) -> bool: ...

    def get_disease(self, disease_id: UUID) -> Disease | None: ...

    def search_diseases(
        self,
        *,
        query: str,
        category_id: UUID | None,
        include_inactive: bool,
    ) -> list[Disease]: ...

    def add_disease(self, disease: Disease) -> None: ...

    def save_disease(self, disease: Disease) -> None: ...
