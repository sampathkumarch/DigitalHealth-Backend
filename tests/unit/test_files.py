from io import BytesIO

from PIL import Image

from app.domain.users import new_member
from app.infrastructure.security.jwt_tokens import JwtAccessTokens
from app.infrastructure.storage.local import LocalStorage
from app.services.files import FileService
from tests.fakes import MemoryStore, MemoryUnitOfWorkFactory
from datetime import datetime, timezone


class _Settings:
    local_storage_dir = ""
    s3_bucket = ""


def _png() -> bytes:
    image = Image.new("RGB", (8, 4), "red")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_profile_photo_records_size_and_dimensions(tmp_path) -> None:
    store = MemoryStore()
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    user = new_member("+91", "9876543210", now)
    store.users[user.id] = user
    settings = _Settings()
    settings.local_storage_dir = str(tmp_path)
    service = FileService(
        MemoryUnitOfWorkFactory(store),
        LocalStorage(settings),  # type: ignore[arg-type]
        JwtAccessTokens("secret", 900, 900),
        max_bytes=5 * 1024 * 1024,
        public_base_url="http://127.0.0.1:8000",
    )
    data = _png()

    stored, updated = service.save_profile_photo(user.id, filename="face.png", data=data)

    assert stored.size_bytes == len(data)
    assert stored.width == 8
    assert stored.height == 4
    assert stored.content_type == "image/png"
    assert updated.profile.photo_file_id == stored.id
    url = service.url_for(stored.id)
    assert url is not None
    assert f"/api/v1/files/{stored.id}/content?access=" in url
    opened = service.open(stored.id, user_id=user.id, access_token=None)
    assert opened.local_path
    assert open(opened.local_path, "rb").read() == data
