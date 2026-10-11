from app.core.config import Settings
from app.infrastructure.storage.local import LocalStorage
from app.infrastructure.storage.s3 import S3Storage
from app.repositories.storage import ObjectStorage


def build_storage(settings: Settings) -> ObjectStorage:
    if settings.s3_bucket:
        return S3Storage(settings)
    return LocalStorage(settings)
