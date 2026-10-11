import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image, UnidentifiedImageError

from app.core.exceptions import NotFoundError, UnauthorizedError, ValidationFailed
from app.core.security import sha256_bytes
from app.domain.files import PROFILE_PHOTO, StoredFile
from app.domain.users import UserAccount
from app.repositories.storage import ObjectStorage
from app.repositories.tokens import AccessTokens
from app.repositories.unit_of_work import UnitOfWorkFactory

logger = logging.getLogger(__name__)

_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


@dataclass(frozen=True)
class FileContent:
    content_type: str
    filename: str
    redirect_url: str | None
    local_path: str | None


class FileService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        storage: ObjectStorage,
        tokens: AccessTokens,
        *,
        max_bytes: int,
        public_base_url: str,
        key_prefix: str = "",
        clock=None,
    ) -> None:
        self._uow_factory = uow_factory
        self._storage = storage
        self._tokens = tokens
        self._max_bytes = max_bytes
        self._public_base_url = public_base_url.rstrip("/")
        self._key_prefix = key_prefix.strip("/")
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def save_profile_photo(
        self,
        user_id: UUID,
        *,
        filename: str,
        data: bytes,
    ) -> tuple[StoredFile, UserAccount]:
        if not data:
            raise ValidationFailed(
                "Could not add that photo. Please try again.",
                {"file": "Could not add that photo. Please try again."},
            )
        if len(data) > self._max_bytes:
            raise ValidationFailed(
                "Image must be 5 MB or smaller.",
                {"file": "Image must be 5 MB or smaller."},
            )
        content_type, width, height = _inspect(data)
        now = self._clock()
        file_id = uuid4()
        key = f"profile-photos/{user_id}/{file_id}"
        if self._key_prefix:
            key = f"{self._key_prefix}/{key}"
        self._storage.put(key, data, content_type)
        with self._uow_factory() as uow:
            user = uow.users.get_by_id(user_id)
            if user is None:
                raise NotFoundError("User not found")
            previous_id = user.profile.photo_file_id
            previous = uow.files.get(previous_id) if previous_id else None
            stored = StoredFile(
                id=file_id,
                owner_user_id=user_id,
                purpose=PROFILE_PHOTO,
                bucket=self._storage.bucket_name,
                storage_key=key,
                original_filename=_safe_name(filename),
                content_type=content_type,
                size_bytes=len(data),
                width=width,
                height=height,
                checksum_sha256=sha256_bytes(data),
                created_at=now,
            )
            uow.files.add(stored)
            user.profile.photo_file_id = stored.id
            user.updated_at = now
            uow.users.save(user)
            uow.commit()
        if previous is not None:
            try:
                self._storage.delete(previous.storage_key)
            except Exception:
                logger.exception("could not delete replaced profile photo")
        return stored, user

    def url_for(self, file_id: UUID | None) -> str | None:
        if file_id is None:
            return None
        with self._uow_factory() as uow:
            record = uow.files.get(file_id)
        if record is None:
            return None
        remote = self._storage.open_url(record.storage_key)
        if remote:
            return remote
        token = self._tokens.issue_file_access(file_id)
        return f"{self._public_base_url}/api/v1/files/{file_id}/content?access={token}"

    def open(
        self,
        file_id: UUID,
        *,
        user_id: UUID | None,
        access_token: str | None,
    ) -> FileContent:
        allowed = user_id is not None and self._owns(file_id, user_id)
        if not allowed and access_token:
            allowed = self._token_matches(file_id, access_token)
        if not allowed:
            raise NotFoundError("File not found")
        with self._uow_factory() as uow:
            record = uow.files.get(file_id)
        if record is None:
            raise NotFoundError("File not found")
        remote = self._storage.open_url(record.storage_key)
        if remote:
            return FileContent(
                content_type=record.content_type,
                filename=record.original_filename,
                redirect_url=remote,
                local_path=None,
            )
        path = self._storage.local_path(record.storage_key)
        if path is None:
            raise NotFoundError("File not found")
        return FileContent(
            content_type=record.content_type,
            filename=record.original_filename,
            redirect_url=None,
            local_path=path,
        )

    def _owns(self, file_id: UUID, user_id: UUID) -> bool:
        with self._uow_factory() as uow:
            record = uow.files.get(file_id)
        return record is not None and record.owner_user_id == user_id

    def _token_matches(self, file_id: UUID, access_token: str) -> bool:
        try:
            return self._tokens.decode_file_access(access_token) == file_id
        except UnauthorizedError:
            return False


def _inspect(data: bytes) -> tuple[str, int, int]:
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
            fmt = (image.format or "").upper()
            width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationFailed(
            "Could not add that photo. Please try again.",
            {"file": "Could not add that photo. Please try again."},
        ) from exc
    content_type = _FORMATS.get(fmt)
    if content_type is None:
        raise ValidationFailed(
            "Use a JPEG, PNG, or WebP image.",
            {"file": "Use a JPEG, PNG, or WebP image."},
        )
    return content_type, width, height


def _safe_name(filename: str) -> str:
    name = Path(filename).name.strip() or "photo"
    return name[:255]
