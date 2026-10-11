import logging
from pathlib import Path

from app.core.config import Settings
from app.core.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class LocalStorage:
    def __init__(self, settings: Settings) -> None:
        self.bucket_name = "local"
        self._root = Path(settings.local_storage_dir).resolve()

    def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def open_url(self, key: str) -> str | None:
        return None

    def local_path(self, key: str) -> str | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return str(path)

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if path != self._root and self._root not in path.parents:
            raise ServiceUnavailable("Invalid storage key.")
        return path
