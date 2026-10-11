from pydantic import BaseModel, field_validator

from app.domain.profile import ProfileSubmission


class ProfileUpdateRequest(BaseModel):
    full_name: str = ""
    email: str = ""
    date_of_birth: str = ""
    weight_kg: str = ""
    blood_group: str = ""
    conditions: list[str] = []
    other_condition: str = ""

    @field_validator(
        "full_name",
        "email",
        "date_of_birth",
        "weight_kg",
        "blood_group",
        "other_condition",
        mode="before",
    )
    @classmethod
    def as_text(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)

    def submission(self) -> ProfileSubmission:
        return ProfileSubmission(
            full_name=self.full_name,
            email=self.email,
            date_of_birth=self.date_of_birth,
            weight_kg=self.weight_kg,
            blood_group=self.blood_group,
            conditions=tuple(self.conditions),
            other_condition=self.other_condition,
        )
