from fastapi import APIRouter

api_router = APIRouter()

# Mount one router per resource:
# from app.api.v1.endpoints import patients
# api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
