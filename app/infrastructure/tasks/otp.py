from app.core.config import settings
from app.infrastructure.messaging.email import EmailSender
from app.infrastructure.messaging.whatsapp import MessagingError, WhatsAppSender
from app.infrastructure.tasks.names import SEND_EMAIL, SEND_WHATSAPP
from app.worker import celery_app


@celery_app.task(
    name=SEND_WHATSAPP,
    autoretry_for=(MessagingError,),
    retry_backoff=True,
    max_retries=3,
)
def send_whatsapp_otp(phone_e164: str, code: str) -> None:
    WhatsAppSender(settings).send(phone_e164, code)


@celery_app.task(
    name=SEND_EMAIL,
    autoretry_for=(MessagingError,),
    retry_backoff=True,
    max_retries=3,
)
def send_email_otp(email: str, code: str) -> None:
    EmailSender(settings).send(email, code)
