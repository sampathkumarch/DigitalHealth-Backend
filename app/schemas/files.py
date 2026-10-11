from uuid import UUID

from pydantic import BaseModel

from app.schemas.auth import ProfileResponse


class StoredFileResponse(BaseModel):
    id: UUID
    content_type: str
    size_bytes: int
    width: int | None
    height: int | None


class PhotoUploadResponse(BaseModel):
    file: StoredFileResponse
    profile: ProfileResponse
