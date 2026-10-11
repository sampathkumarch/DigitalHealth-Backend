import logging

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class MessagingError(Exception):
    """The provider was configured and the send failed. Celery retries these."""


class WhatsAppSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, phone_e164: str, code: str) -> None:
        settings = self._settings
        if not settings.whatsapp_token or not settings.whatsapp_phone_number_id:
            logger.warning("whatsapp is not configured; otp kept in the database")
            return
        url = (
            f"https://graph.facebook.com/{settings.whatsapp_api_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_e164.lstrip("+"),
            "type": "template",
            "template": {
                "name": settings.whatsapp_template_name,
                "language": {"code": settings.whatsapp_template_language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": code}],
                    }
                ],
            },
        }
        try:
            response = httpx.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {settings.whatsapp_token}"},
                timeout=10,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise MessagingError("WhatsApp send failed") from exc
