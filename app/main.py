from fastapi import FastAPI

from app.api.endpoints import health, meta
from app.api.exception_handlers import register_exception_handlers
from app.api.middleware import RequestIdMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    """Composition root. Wire adapters here, not inside services."""
    setup_logging()
    application = FastAPI(title=settings.app_name, debug=settings.debug)
    application.add_middleware(RequestIdMiddleware)
    register_exception_handlers(application)
    application.include_router(meta.router)
    application.include_router(health.router)
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
