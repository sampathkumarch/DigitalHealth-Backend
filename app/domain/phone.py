import re
from dataclasses import dataclass

from app.domain.errors import DomainError

_RULES = {
    "+91": re.compile(r"^[6-9]\d{9}$"),
}


@dataclass(frozen=True)
class PhoneNumber:
    country_code: str
    national: str

    @property
    def e164(self) -> str:
        return f"{self.country_code}{self.national}"


def normalize_phone(country_code: str, phone: str) -> PhoneNumber:
    code = country_code.strip()
    digits = re.sub(r"\D", "", phone)
    pattern = _RULES.get(code)
    if pattern is None or pattern.match(digits) is None:
        raise DomainError(
            "Enter a valid 10-digit WhatsApp number.",
            {"phone": "Enter a valid 10-digit WhatsApp number."},
        )
    return PhoneNumber(country_code=code, national=digits)
