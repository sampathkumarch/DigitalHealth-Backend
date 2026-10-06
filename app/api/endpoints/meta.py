from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["meta"])


@router.get("/")
def root() -> dict[str, str]:
    return {"message": f"Welcome to {settings.app_name}"}
