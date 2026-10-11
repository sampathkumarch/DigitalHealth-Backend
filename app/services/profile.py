from datetime import datetime, timezone
from uuid import UUID

from app.core.exceptions import ConflictError, NotFoundError, ValidationFailed
from app.domain.errors import DomainError
from app.domain.profile import ProfileData, ProfileSubmission, validate_profile
from app.domain.users import UserAccount
from app.repositories.errors import DuplicateRecord
from app.repositories.unit_of_work import UnitOfWorkFactory


class ProfileService:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock=None) -> None:
        self._uow_factory = uow_factory
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def update(self, user_id: UUID, submission: ProfileSubmission) -> UserAccount:
        with self._uow_factory() as uow:
            user = uow.users.get_by_id(user_id)
            if user is None:
                raise NotFoundError("User not found")
            cleaned = _clean(submission, require_email_field=not user.profile.profile_completed)
            if cleaned.email is not None:
                owner = uow.users.get_by_email(cleaned.email)
                if owner is not None and owner.id != user.id:
                    raise ConflictError("That email is already in use.")
            _apply(user, cleaned, self._clock())
            try:
                uow.users.save(user)
                uow.commit()
            except DuplicateRecord as exc:
                raise ConflictError("That email is already in use.") from exc
            return user


def _clean(submission: ProfileSubmission, *, require_email_field: bool) -> ProfileData:
    try:
        return validate_profile(submission, require_email_field=require_email_field)
    except DomainError as exc:
        raise ValidationFailed(exc.message, exc.fields) from exc


def _apply(user: UserAccount, cleaned: ProfileData, now: datetime) -> None:
    if cleaned.email is not None and cleaned.email == user.email and user.email_verified_at:
        verified_at = user.email_verified_at
    else:
        verified_at = None
    user.email = cleaned.email
    user.email_verified_at = verified_at
    user.profile.full_name = cleaned.full_name
    user.profile.date_of_birth = cleaned.date_of_birth
    user.profile.weight_kg = cleaned.weight_kg
    user.profile.blood_group = cleaned.blood_group
    user.profile.conditions = cleaned.conditions
    user.profile.other_condition = cleaned.other_condition
    user.profile.profile_completed = True
    user.updated_at = now
