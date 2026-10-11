import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings
from app.infrastructure.messaging.whatsapp import MessagingError

logger = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, email: str, code: str) -> None:
        settings = self._settings
        if not settings.smtp_host:
            logger.warning("smtp is not configured; otp kept in the database")
            return
        message = EmailMessage()
        message["Subject"] = f"{settings.app_name} verification code"
        message["From"] = settings.smtp_from or settings.smtp_user
        message["To"] = email
        message.set_content(
            f"Your verification code is {code}. It expires in {settings.otp_ttl_seconds // 60} minutes."
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password.replace(" ", ""))
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise MessagingError("Email send failed") from exc
