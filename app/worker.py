import logging

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings
from app.core.logging import setup_logging
from app.infrastructure.tasks.names import SEND_EMAIL, SEND_WHATSAPP

logger = logging.getLogger(__name__)

celery_app = Celery(
    "digital_health",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.update(
    task_ignore_result=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    task_default_queue="otp",
    timezone="UTC",
    enable_utc=True,
    imports=("app.infrastructure.tasks.otp",),
)


@worker_process_init.connect
def _configure_worker_logging(**_kwargs: object) -> None:
    setup_logging()


class CeleryOtpDispatcher:
    def dispatch_whatsapp(self, phone_e164: str, code: str) -> None:
        self._enqueue(SEND_WHATSAPP, [phone_e164, code])

    def dispatch_email(self, email: str, code: str) -> None:
        self._enqueue(SEND_EMAIL, [email, code])

    def _enqueue(self, name: str, args: list[str]) -> None:
        try:
            celery_app.send_task(name, args=args)
        except Exception:
            logger.exception("failed to enqueue %s", name)
