from typing import Protocol


class OtpDispatcher(Protocol):
    def dispatch_whatsapp(self, phone_e164: str, code: str) -> None: ...

    def dispatch_email(self, email: str, code: str) -> None: ...
