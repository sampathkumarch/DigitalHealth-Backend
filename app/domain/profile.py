import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.domain.errors import DomainError

BLOOD_GROUPS = ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-")
MEDICAL_CONDITIONS = (
    "Diabetes",
    "Hypertension",
    "Asthma",
    "Heart disease",
    "Thyroid",
    "None",
    "Other",
)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_MIN_DOB = date(1900, 1, 1)


@dataclass(frozen=True)
class ProfileSubmission:
    full_name: str
    email: str
    date_of_birth: str
    weight_kg: str
    blood_group: str
    conditions: tuple[str, ...]
    other_condition: str


@dataclass(frozen=True)
class ProfileData:
    full_name: str
    email: str | None
    date_of_birth: date | None
    weight_kg: Decimal | None
    blood_group: str | None
    conditions: tuple[str, ...]
    other_condition: str


def normalize_email(email: str) -> str | None:
    """Return a lowercase address, or None when the field was left empty."""
    cleaned = email.strip().lower()
    if not cleaned:
        return None
    if len(cleaned) > 320 or EMAIL_PATTERN.match(cleaned) is None:
        raise DomainError(
            "Please enter a valid email address.",
            {"email": "Please enter a valid email address."},
        )
    return cleaned


def require_email(email: str) -> str:
    normalized = normalize_email(email)
    if normalized is None:
        raise DomainError(
            "Please enter a valid email address.",
            {"email": "Please enter a valid email address."},
        )
    return normalized


def validate_profile(submission: ProfileSubmission, *, require_email_field: bool) -> ProfileData:
    errors: dict[str, str] = {}

    full_name = submission.full_name.strip()
    if not full_name:
        errors["full_name"] = "Please enter your full name."
    elif len(full_name) > 120:
        errors["full_name"] = "Full name must be 120 characters or fewer."

    email: str | None = None
    raw_email = submission.email.strip()
    if require_email_field or raw_email:
        try:
            email = require_email(raw_email) if require_email_field or raw_email else None
            if raw_email:
                email = normalize_email(raw_email)
        except DomainError as exc:
            errors.update(exc.fields)

    dob = _parse_dob(submission.date_of_birth, errors)
    weight = _parse_weight(submission.weight_kg, errors)
    blood = _parse_blood(submission.blood_group, errors)
    conditions, other = _parse_conditions(
        submission.conditions,
        submission.other_condition,
        errors,
    )

    if errors:
        raise DomainError(next(iter(errors.values())), errors)

    return ProfileData(
        full_name=full_name,
        email=email,
        date_of_birth=dob,
        weight_kg=weight,
        blood_group=blood,
        conditions=conditions,
        other_condition=other,
    )


def format_dob(value: date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d/%m/%Y")


def format_weight(value: Decimal | None) -> str:
    if value is None:
        return ""
    text = f"{value:.1f}"
    if text.endswith(".0"):
        return text[:-2]
    return text


def _parse_dob(raw: str, errors: dict[str, str]) -> date | None:
    text = raw.strip()
    if not text:
        return None
    parsed = _parse_date(text)
    if parsed is None or parsed < _MIN_DOB or parsed > date.today():
        errors["date_of_birth"] = "Choose a valid date of birth."
        return None
    return parsed


def _parse_date(text: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_weight(raw: str, errors: dict[str, str]) -> Decimal | None:
    text = raw.strip()
    if not text:
        return None
    if not re.fullmatch(r"\d+(\.\d)?", text):
        errors["weight"] = "Enter a valid weight in kg."
        return None
    try:
        weight = Decimal(text)
    except InvalidOperation:
        errors["weight"] = "Enter a valid weight in kg."
        return None
    if weight <= 0 or weight > 500:
        errors["weight"] = "Enter a valid weight in kg."
        return None
    return weight


def _parse_blood(raw: str, errors: dict[str, str]) -> str | None:
    text = raw.strip()
    if not text:
        return None
    if text not in BLOOD_GROUPS:
        errors["blood_group"] = "Select a valid blood group."
        return None
    return text


def _parse_conditions(
    raw: tuple[str, ...],
    other_raw: str,
    errors: dict[str, str],
) -> tuple[tuple[str, ...], str]:
    seen: list[str] = []
    for item in raw:
        if item not in seen:
            seen.append(item)
    unknown = [item for item in seen if item not in MEDICAL_CONDITIONS]
    if unknown:
        errors["conditions"] = "Select a valid medical condition."
    if "None" in seen and len(seen) > 1:
        errors["conditions"] = "Choose None on its own, or pick specific conditions."
    other = other_raw.strip()
    if "Other" in seen:
        if not other:
            errors["other_condition"] = "Please specify the condition."
        elif len(other) > 200:
            errors["other_condition"] = "Keep the condition under 200 characters."
    else:
        other = ""
    return tuple(seen), other
