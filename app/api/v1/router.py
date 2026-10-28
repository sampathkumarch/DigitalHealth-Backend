from fastapi import APIRouter

from app.api.v1.endpoints import auth, diagnoses, diseases, files, profile, screen_time

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(diagnoses.router)
api_router.include_router(diseases.categories)
api_router.include_router(diseases.diseases)
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(screen_time.router)
