from datetime import datetime
from uuid import UUID

from app.domain.diseases import SEARCH_LIMIT, Disease, DiseaseCategory, UserDiagnosis
from app.domain.files import StoredFile
from app.domain.otp import OtpChallenge
from app.domain.tokens import RefreshToken
from app.domain.users import UserAccount
from app.repositories.errors import DuplicateRecord


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[UUID, UserAccount] = {}
        self.otps: list[OtpChallenge] = []
        self.tokens: dict[UUID, RefreshToken] = {}
        self.files: dict[UUID, StoredFile] = {}
        self.categories: dict[UUID, DiseaseCategory] = {}
        self.diseases: dict[UUID, Disease] = {}
        self.diagnoses: dict[UUID, UserDiagnosis] = {}


class MemoryUsers:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def get_by_id(self, user_id: UUID) -> UserAccount | None:
        return self._store.users.get(user_id)

    def get_by_phone(self, country_code: str, phone: str) -> UserAccount | None:
        for user in self._store.users.values():
            if user.country_code == country_code and user.phone == phone:
                return user
        return None

    def get_by_email(self, email: str) -> UserAccount | None:
        for user in self._store.users.values():
            if user.email == email:
                return user
        return None

    def add(self, user: UserAccount) -> None:
        if self.get_by_phone(user.country_code, user.phone) is not None:
            raise DuplicateRecord("phone")
        if user.email and self.get_by_email(user.email) is not None:
            raise DuplicateRecord("email")
        self._store.users[user.id] = user

    def save(self, user: UserAccount) -> None:
        owner = self.get_by_email(user.email) if user.email else None
        if owner is not None and owner.id != user.id:
            raise DuplicateRecord("email")
        self._store.users[user.id] = user


class MemoryOtps:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, challenge: OtpChallenge) -> None:
        self._store.otps.append(challenge)

    def save(self, challenge: OtpChallenge) -> None:
        return None

    def get_latest(self, *, channel: str, destination: str, purpose: str) -> OtpChallenge | None:
        matches = [
            item
            for item in self._store.otps
            if item.channel == channel and item.destination == destination and item.purpose == purpose
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.created_at)

    def invalidate_active(self, *, channel: str, destination: str, purpose: str, now: datetime) -> None:
        for item in self._store.otps:
            if (
                item.channel == channel
                and item.destination == destination
                and item.purpose == purpose
                and item.consumed_at is None
            ):
                item.consumed_at = now

    def consume(self, challenge_id: UUID, now: datetime) -> bool:
        for item in self._store.otps:
            if item.id == challenge_id:
                if item.consumed_at is not None:
                    return False
                item.consumed_at = now
                return True
        return False


class MemoryTokens:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, token: RefreshToken) -> None:
        self._store.tokens[token.id] = token

    def save(self, token: RefreshToken) -> None:
        self._store.tokens[token.id] = token

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._store.tokens.values():
            if token.token_hash == token_hash:
                return token
        return None

    def revoke_all(self, user_id: UUID, now: datetime) -> None:
        for token in self._store.tokens.values():
            if token.user_id == user_id and token.revoked_at is None:
                token.revoked_at = now


class MemoryFiles:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def add(self, stored: StoredFile) -> None:
        self._store.files[stored.id] = stored

    def get(self, file_id: UUID) -> StoredFile | None:
        return self._store.files.get(file_id)


class MemoryDiseases:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def list_categories(self) -> list[DiseaseCategory]:
        return sorted(self._store.categories.values(), key=lambda item: item.name.casefold())

    def get_category(self, category_id: UUID) -> DiseaseCategory | None:
        return self._store.categories.get(category_id)

    def add_category(self, category: DiseaseCategory) -> None:
        for existing in self._store.categories.values():
            if existing.name.casefold() == category.name.casefold():
                raise DuplicateRecord("category")
        self._store.categories[category.id] = category

    def save_category(self, category: DiseaseCategory) -> None:
        for existing in self._store.categories.values():
            if existing.id != category.id and existing.name.casefold() == category.name.casefold():
                raise DuplicateRecord("category")
        self._store.categories[category.id] = category

    def delete_category(self, category_id: UUID) -> bool:
        if category_id not in self._store.categories:
            return False
        for disease in self._store.diseases.values():
            if disease.category_id == category_id:
                disease.category_id = None
                disease.category_name = ""
        del self._store.categories[category_id]
        return True

    def get_disease(self, disease_id: UUID) -> Disease | None:
        disease = self._store.diseases.get(disease_id)
        if disease is None:
            return None
        return self._with_category(disease)

    def search_diseases(
        self,
        *,
        query: str,
        category_id: UUID | None,
        include_inactive: bool,
    ) -> list[Disease]:
        needle = query.casefold()
        found: list[Disease] = []
        for disease in self._store.diseases.values():
            if not include_inactive and not disease.is_active:
                continue
            if category_id is not None and disease.category_id != category_id:
                continue
            code = (disease.code or "").casefold()
            if needle and needle not in disease.name.casefold() and needle not in code:
                continue
            found.append(self._with_category(disease))
        found.sort(key=lambda item: item.name.casefold())
        return found[:SEARCH_LIMIT]

    def add_disease(self, disease: Disease) -> None:
        self._reject_duplicate_code(disease)
        self._store.diseases[disease.id] = disease

    def save_disease(self, disease: Disease) -> None:
        self._reject_duplicate_code(disease)
        self._store.diseases[disease.id] = disease

    def _reject_duplicate_code(self, disease: Disease) -> None:
        if not disease.code or not disease.code_system:
            return
        for existing in self._store.diseases.values():
            if existing.id == disease.id:
                continue
            if (
                existing.code == disease.code
                and (existing.code_system or "").casefold() == disease.code_system.casefold()
            ):
                raise DuplicateRecord("code")

    def _with_category(self, disease: Disease) -> Disease:
        if disease.category_id is None:
            disease.category_name = ""
            return disease
        category = self._store.categories.get(disease.category_id)
        disease.category_name = category.name if category else ""
        return disease


class MemoryDiagnoses:
    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def list_for_user(self, user_id: UUID) -> list[UserDiagnosis]:
        rows = [item for item in self._store.diagnoses.values() if item.user_id == user_id]
        rows.sort(key=lambda item: (item.created_at, str(item.id)))
        return [self._with_disease(item) for item in rows]

    def get(self, diagnosis_id: UUID) -> UserDiagnosis | None:
        row = self._store.diagnoses.get(diagnosis_id)
        if row is None:
            return None
        return self._with_disease(row)

    def add(self, diagnosis: UserDiagnosis) -> None:
        self._reject_duplicate(diagnosis)
        self._store.diagnoses[diagnosis.id] = diagnosis

    def save(self, diagnosis: UserDiagnosis) -> None:
        self._reject_duplicate(diagnosis)
        self._store.diagnoses[diagnosis.id] = diagnosis

    def delete(self, diagnosis_id: UUID) -> None:
        self._store.diagnoses.pop(diagnosis_id, None)

    def find_catalog_duplicate(self, user_id: UUID, disease_id: UUID) -> UserDiagnosis | None:
        for item in self._store.diagnoses.values():
            if item.user_id == user_id and item.disease_id == disease_id:
                return item
        return None

    def find_custom_duplicate(self, user_id: UUID, name: str) -> UserDiagnosis | None:
        key = name.casefold()
        for item in self._store.diagnoses.values():
            if item.user_id == user_id and item.custom_disease_name and item.custom_disease_name.casefold() == key:
                return item
        return None

    def _reject_duplicate(self, diagnosis: UserDiagnosis) -> None:
        if diagnosis.disease_id is not None:
            other = self.find_catalog_duplicate(diagnosis.user_id, diagnosis.disease_id)
            if other is not None and other.id != diagnosis.id:
                raise DuplicateRecord("disease")
        if diagnosis.custom_disease_name:
            other = self.find_custom_duplicate(diagnosis.user_id, diagnosis.custom_disease_name)
            if other is not None and other.id != diagnosis.id:
                raise DuplicateRecord("custom")

    def _with_disease(self, diagnosis: UserDiagnosis) -> UserDiagnosis:
        if diagnosis.disease_id is None:
            diagnosis.disease_name = None
            diagnosis.disease_code = None
            diagnosis.code_system = None
            return diagnosis
        disease = self._store.diseases.get(diagnosis.disease_id)
        if disease is None:
            return diagnosis
        diagnosis.disease_name = disease.name
        diagnosis.disease_code = disease.code
        diagnosis.code_system = disease.code_system
        return diagnosis


class MemoryUnitOfWork:
    def __init__(self, store: MemoryStore) -> None:
        self.users = MemoryUsers(store)
        self.otps = MemoryOtps(store)
        self.tokens = MemoryTokens(store)
        self.files = MemoryFiles(store)
        self.diseases = MemoryDiseases(store)
        self.diagnoses = MemoryDiagnoses(store)

    def __enter__(self) -> "MemoryUnitOfWork":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class MemoryUnitOfWorkFactory:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def __call__(self) -> MemoryUnitOfWork:
        return MemoryUnitOfWork(self.store)


class RecordingDispatcher:
    def __init__(self) -> None:
        self.whatsapp: list[tuple[str, str]] = []
        self.email: list[tuple[str, str]] = []

    def dispatch_whatsapp(self, phone_e164: str, code: str) -> None:
        self.whatsapp.append((phone_e164, code))

    def dispatch_email(self, email: str, code: str) -> None:
        self.email.append((email, code))
