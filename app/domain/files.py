from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

PROFILE_PHOTO = "profile_photo"


@dataclass
class StoredFile:
    id: UUID
    owner_user_id: UUID
    purpose: str
    bucket: str
    storage_key: str
    original_filename: str
    content_type: str
    size_bytes: int
    width: int | None
    height: int | None
    checksum_sha256: str
    created_at: datetime
