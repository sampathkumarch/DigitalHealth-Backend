from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.files import StoredFile
from app.domain.otp import OtpChallenge
from app.domain.tokens import RefreshToken
from app.domain.users import HealthProfile, UserAccount
from app.infrastructure.db.models import (
    FileModel,
    OtpChallengeModel,
    RefreshTokenModel,
    UserConditionModel,
    UserModel,
    UserProfileModel,
)
from app.repositories.errors import DuplicateRecord


def _duplicate(exc: IntegrityError) -> DuplicateRecord:
    text = str(getattr(exc, "orig", exc)).lower()
    if "email" in text:
        return DuplicateRecord("email")
    return DuplicateRecord("phone")


def _to_user(
    row: UserModel,
    profile: UserProfileModel | None,
    conditions: list[str],
) -> UserAccount:
    health = HealthProfile()
    if profile is not None:
        weight = profile.weight_kg
        health = HealthProfile(
            full_name=profile.full_name,
            date_of_birth=profile.date_of_birth,
            weight_kg=Decimal(weight) if weight is not None else None,
            blood_group=profile.blood_group,
            conditions=tuple(conditions),
            other_condition=profile.other_condition or "",
            photo_file_id=profile.photo_file_id,
            profile_completed=profile.profile_completed,
        )
    return UserAccount(
        id=row.id,
        country_code=row.country_code,
        phone=row.phone,
        phone_verified_at=row.phone_verified_at,
        email=row.email,
        email_verified_at=row.email_verified_at,
        role=row.role,
        status=row.status,
        profile=health,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        row = self._session.get(UserModel, user_id)
        if row is None:
            return None
        return self._assemble(row)

    def get_by_phone(self, country_code: str, phone: str) -> UserAccount | None:
        row = self._session.scalar(
            select(UserModel).where(
                UserModel.country_code == country_code,
                UserModel.phone == phone,
            )
        )
        if row is None:
            return None
        return self._assemble(row)

    def get_by_email(self, email: str) -> UserAccount | None:
        row = self._session.scalar(select(UserModel).where(UserModel.email == email))
        if row is None:
            return None
        return self._assemble(row)

    def add(self, user: UserAccount) -> None:
        self._session.add(
            UserModel(
                id=user.id,
                country_code=user.country_code,
                phone=user.phone,
                phone_verified_at=user.phone_verified_at,
                email=user.email,
                email_verified_at=user.email_verified_at,
                role=user.role,
                status=user.status,
                created_at=user.created_at,
                updated_at=user.updated_at,
            )
        )
        self._session.add(self._profile_row(user))
        self._replace_conditions(user)
        self._flush()

    def save(self, user: UserAccount) -> None:
        row = self._session.get(UserModel, user.id)
        if row is None:
            return
        row.country_code = user.country_code
        row.phone = user.phone
        row.phone_verified_at = user.phone_verified_at
        row.email = user.email
        row.email_verified_at = user.email_verified_at
        row.role = user.role
        row.status = user.status
        row.updated_at = user.updated_at
        profile = self._session.get(UserProfileModel, user.id)
        if profile is None:
            self._session.add(self._profile_row(user))
        else:
            self._apply_profile(profile, user)
        self._replace_conditions(user)
        self._flush()

    def _assemble(self, row: UserModel) -> UserAccount:
        profile = self._session.get(UserProfileModel, row.id)
        conditions = list(
            self._session.scalars(
                select(UserConditionModel.condition)
                .where(UserConditionModel.user_id == row.id)
                .order_by(UserConditionModel.position)
            ).all()
        )
        return _to_user(row, profile, conditions)

    def _profile_row(self, user: UserAccount) -> UserProfileModel:
        profile = user.profile
        return UserProfileModel(
            user_id=user.id,
            full_name=profile.full_name,
            date_of_birth=profile.date_of_birth,
            weight_kg=profile.weight_kg,
            blood_group=profile.blood_group,
            other_condition=profile.other_condition or None,
            photo_file_id=profile.photo_file_id,
            profile_completed=profile.profile_completed,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _apply_profile(self, row: UserProfileModel, user: UserAccount) -> None:
        profile = user.profile
        row.full_name = profile.full_name
        row.date_of_birth = profile.date_of_birth
        row.weight_kg = profile.weight_kg
        row.blood_group = profile.blood_group
        row.other_condition = profile.other_condition or None
        row.photo_file_id = profile.photo_file_id
        row.profile_completed = profile.profile_completed
        row.updated_at = user.updated_at

    def _replace_conditions(self, user: UserAccount) -> None:
        existing = list(
            self._session.scalars(
                select(UserConditionModel).where(UserConditionModel.user_id == user.id)
            ).all()
        )
        for row in existing:
            self._session.delete(row)
        if existing:
            self._session.flush()
        for index, condition in enumerate(user.profile.conditions):
            self._session.add(
                UserConditionModel(user_id=user.id, condition=condition, position=index)
            )

    def _flush(self) -> None:
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise _duplicate(exc) from exc


class SqlOtpRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, challenge: OtpChallenge) -> None:
        self._session.add(
            OtpChallengeModel(
                id=challenge.id,
                user_id=challenge.user_id,
                channel=challenge.channel,
                destination=challenge.destination,
                purpose=challenge.purpose,
                code_hash=challenge.code_hash,
                code_plaintext=challenge.code_plaintext,
                expires_at=challenge.expires_at,
                attempt_count=challenge.attempt_count,
                max_attempts=challenge.max_attempts,
                consumed_at=challenge.consumed_at,
                created_at=challenge.created_at,
            )
        )
        self._session.flush()

    def save(self, challenge: OtpChallenge) -> None:
        row = self._session.get(OtpChallengeModel, challenge.id)
        if row is None:
            return
        row.attempt_count = challenge.attempt_count
        row.consumed_at = challenge.consumed_at
        self._session.flush()

    def get_latest(
        self,
        *,
        channel: str,
        destination: str,
        purpose: str,
    ) -> OtpChallenge | None:
        row = self._session.scalar(
            select(OtpChallengeModel)
            .where(
                OtpChallengeModel.channel == channel,
                OtpChallengeModel.destination == destination,
                OtpChallengeModel.purpose == purpose,
            )
            .order_by(OtpChallengeModel.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return _to_otp(row)

    def invalidate_active(
        self,
        *,
        channel: str,
        destination: str,
        purpose: str,
        now: datetime,
    ) -> None:
        rows = self._session.scalars(
            select(OtpChallengeModel).where(
                OtpChallengeModel.channel == channel,
                OtpChallengeModel.destination == destination,
                OtpChallengeModel.purpose == purpose,
                OtpChallengeModel.consumed_at.is_(None),
            )
        ).all()
        for row in rows:
            row.consumed_at = now
        self._session.flush()

    def consume(self, challenge_id: UUID, now: datetime) -> bool:
        row = self._session.get(OtpChallengeModel, challenge_id)
        if row is None or row.consumed_at is not None:
            return False
        row.consumed_at = now
        self._session.flush()
        return True


class SqlRefreshTokenRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, token: RefreshToken) -> None:
        self._session.add(
            RefreshTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                revoked_at=token.revoked_at,
                replaced_by_id=token.replaced_by_id,
                created_at=token.created_at,
            )
        )
        self._session.flush()

    def save(self, token: RefreshToken) -> None:
        row = self._session.get(RefreshTokenModel, token.id)
        if row is None:
            return
        row.revoked_at = token.revoked_at
        row.replaced_by_id = token.replaced_by_id
        self._session.flush()

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        row = self._session.scalar(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        if row is None:
            return None
        return RefreshToken(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            replaced_by_id=row.replaced_by_id,
            created_at=row.created_at,
        )

    def revoke_all(self, user_id: UUID, now: datetime) -> None:
        rows = self._session.scalars(
            select(RefreshTokenModel).where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
        ).all()
        for row in rows:
            row.revoked_at = now
        self._session.flush()


class SqlFileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, stored: StoredFile) -> None:
        self._session.add(
            FileModel(
                id=stored.id,
                owner_user_id=stored.owner_user_id,
                purpose=stored.purpose,
                bucket=stored.bucket,
                storage_key=stored.storage_key,
                original_filename=stored.original_filename,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
                width=stored.width,
                height=stored.height,
                checksum_sha256=stored.checksum_sha256,
                created_at=stored.created_at,
            )
        )
        self._session.flush()

    def get(self, file_id: UUID) -> StoredFile | None:
        row = self._session.get(FileModel, file_id)
        if row is None:
            return None
        return StoredFile(
            id=row.id,
            owner_user_id=row.owner_user_id,
            purpose=row.purpose,
            bucket=row.bucket,
            storage_key=row.storage_key,
            original_filename=row.original_filename,
            content_type=row.content_type,
            size_bytes=row.size_bytes,
            width=row.width,
            height=row.height,
            checksum_sha256=row.checksum_sha256,
            created_at=row.created_at,
        )


def _to_otp(row: OtpChallengeModel) -> OtpChallenge:
    return OtpChallenge(
        id=row.id,
        user_id=row.user_id,
        channel=row.channel,
        destination=row.destination,
        purpose=row.purpose,
        code_hash=row.code_hash,
        code_plaintext=row.code_plaintext,
        expires_at=row.expires_at,
        attempt_count=row.attempt_count,
        max_attempts=row.max_attempts,
        consumed_at=row.consumed_at,
        created_at=row.created_at,
    )
