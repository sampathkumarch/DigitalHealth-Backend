from typing import Protocol
from uuid import UUID

from app.domain.files import StoredFile


class FileRepository(Protocol):
    def add(self, stored: StoredFile) -> None: ...

    def get(self, file_id: UUID) -> StoredFile | None: ...
