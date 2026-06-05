from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.pagination.schemas import SortingMethod
from app.common.pagination.sqlalchemy import apply_sorting, model_sort_columns
from app.modules.users.domain.entities import PhoneNumber, User, UserPreferences, UserProfile
from app.modules.users.domain.enums import UserLanguage, UserRole, UserStatus, UserTheme
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.sqlalchemy_models import UserModel, UserPreferencesModel, UserProfileModel


def _to_entity(model: UserModel) -> User:
    profile_uploaded = bool(getattr(model, "profile_completed_at", None))
    return User(
        id=model.id,
        email=model.email,
        role=UserRole(model.role),
        status=UserStatus(model.status),
        is_verified=model.is_verified,
        created_at=model.created_at,
        is_user_data_uploaded=profile_uploaded,
    )


def _profile_entity(model: UserProfileModel) -> UserProfile:
    return UserProfile(
        user_id=model.user_id,
        full_name=model.full_name,
        phone_number=_phone_number_entity(model.country_code, model.dial_code, model.phone_number),
        avatar_url=model.avatar_url,
        avatar_object_key=model.avatar_object_key,
        created_at=model.created_at,
        updated_at=model.updated_at,
        completed_at=model.completed_at,
    )


def _phone_number_entity(
    country_code: str | None,
    dial_code: str | None,
    number: str | None,
) -> PhoneNumber | None:
    if dial_code is None or number is None:
        return None
    if not dial_code.startswith('+'):
        return None
    if not number.isdigit():
        return None
    return PhoneNumber(country_code=country_code, dial_code=dial_code, number=number)


def _preferences_entity(model: UserPreferencesModel) -> UserPreferences:
    return UserPreferences(
        user_id=model.user_id,
        language=UserLanguage(model.language),
        theme=UserTheme(model.theme),
        push_notifications_enabled=model.push_notifications_enabled,
        email_notifications_enabled=model.email_notifications_enabled,
        marketing_notifications_enabled=model.marketing_notifications_enabled,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


_USER_SORT_COLUMNS = {
    **model_sort_columns(UserModel),
    "full_name": UserProfileModel.full_name,
    "phone_number": UserProfileModel.phone_number,
}


def _with_profile_uploaded(stmt):
    return stmt.add_columns(UserProfileModel.completed_at.label("profile_completed_at")).outerjoin(
        UserProfileModel,
        UserProfileModel.user_id == UserModel.id,
    )


def _user_from_row(row) -> User:
    model = row[0]
    model.profile_completed_at = row[1]
    return _to_entity(model)


def _user_conditions(
    *,
    role: UserRole | None = None,
    status: UserStatus | None = None,
    search: str | None = None,
) -> list:
    conditions = []
    if role is not None:
        conditions.append(UserModel.role == role.value)
    if status is not None:
        conditions.append(UserModel.status == status.value)
    if search:
        pattern = f"%{search.strip()}%"
        conditions.append(
            or_(
                UserModel.email.ilike(pattern),
                UserProfileModel.full_name.ilike(pattern),
                UserProfileModel.phone_number.ilike(pattern),
            ),
        )
    return conditions


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        stmt = _with_profile_uploaded(select(UserModel)).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        return _user_from_row(row) if row is not None else None

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = _with_profile_uploaded(select(UserModel)).where(UserModel.id == user_id)
        result = await self._session.execute(stmt)
        row = result.one_or_none()
        return _user_from_row(row) if row is not None else None

    async def get_or_create(self, email: str, now: datetime) -> User:
        existing = await self.get_by_email(email)
        if existing is not None:
            return existing
        row = UserModel(
            id=uuid4(),
            email=email,
            role=UserRole.USER.value,
            status=UserStatus.ACTIVE.value,
            is_verified=False,
            created_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_entity(row)

    async def set_verified(self, user_id: UUID, value: bool) -> None:
        result = await self._session.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        if row is not None:
            row.is_verified = value

    async def count_users(
        self,
        *,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> int:
        conditions = _user_conditions(role=role, status=status, search=search)
        stmt = select(func.count()).select_from(UserModel).outerjoin(UserProfileModel).where(*conditions)
        result = await self._session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
        sort_key: str = "created_at",
        sorting_method: SortingMethod = SortingMethod.DESC,
    ) -> list[User]:
        conditions = _user_conditions(role=role, status=status, search=search)
        stmt = apply_sorting(
            _with_profile_uploaded(select(UserModel)).where(*conditions),
            sort_key=sort_key,
            sorting_method=sorting_method,
            sort_columns=_USER_SORT_COLUMNS,
        )
        stmt = stmt.offset(offset).limit(limit)
        result = await self._session.execute(stmt)
        return [_user_from_row(row) for row in result.all()]

    async def update_role(self, user_id: UUID, role: UserRole) -> User | None:
        stmt = update(UserModel).where(UserModel.id == user_id).values(role=role.value).returning(UserModel)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row is not None else None

    async def update_status(self, user_id: UUID, status: UserStatus) -> User | None:
        stmt = update(UserModel).where(UserModel.id == user_id).values(status=status.value).returning(UserModel)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_entity(row) if row is not None else None

    async def get_profile(self, user_id: UUID) -> UserProfile | None:
        result = await self._session.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
        row = result.scalar_one_or_none()
        return _profile_entity(row) if row is not None else None

    async def create_profile(
        self,
        *,
        user_id: UUID,
        full_name: str,
        phone_number: PhoneNumber | None,
        now: datetime,
    ) -> UserProfile:
        row = UserProfileModel(
            user_id=user_id,
            full_name=full_name,
            country_code=phone_number.country_code if phone_number is not None else None,
            dial_code=phone_number.dial_code if phone_number is not None else None,
            phone_number=phone_number.number if phone_number is not None else None,
            avatar_url=None,
            avatar_object_key=None,
            created_at=now,
            updated_at=now,
            completed_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _profile_entity(row)

    async def update_profile(
        self,
        *,
        user_id: UUID,
        full_name: str | None,
        phone_number: PhoneNumber | None,
        now: datetime,
    ) -> UserProfile | None:
        result = await self._session.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if full_name is not None:
            row.full_name = full_name
        if phone_number is not None:
            row.country_code = phone_number.country_code
            row.dial_code = phone_number.dial_code
            row.phone_number = phone_number.number
        row.updated_at = now
        if row.completed_at is None:
            row.completed_at = now
        await self._session.flush()
        return _profile_entity(row)

    async def update_avatar(
        self,
        *,
        user_id: UUID,
        avatar_url: str,
        avatar_object_key: str,
        now: datetime,
    ) -> UserProfile | None:
        result = await self._session.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.avatar_url = avatar_url
        row.avatar_object_key = avatar_object_key
        row.updated_at = now
        await self._session.flush()
        return _profile_entity(row)

    async def clear_avatar(self, *, user_id: UUID, now: datetime) -> UserProfile | None:
        result = await self._session.execute(select(UserProfileModel).where(UserProfileModel.user_id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.avatar_url = None
        row.avatar_object_key = None
        row.updated_at = now
        await self._session.flush()
        return _profile_entity(row)

    async def get_preferences(self, user_id: UUID) -> UserPreferences | None:
        result = await self._session.execute(
            select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id),
        )
        row = result.scalar_one_or_none()
        return _preferences_entity(row) if row is not None else None

    async def create_preferences(
        self,
        *,
        user_id: UUID,
        language: UserLanguage,
        theme: UserTheme,
        push_notifications_enabled: bool,
        email_notifications_enabled: bool,
        marketing_notifications_enabled: bool,
        now: datetime,
    ) -> UserPreferences:
        row = UserPreferencesModel(
            user_id=user_id,
            language=language.value,
            theme=theme.value,
            push_notifications_enabled=push_notifications_enabled,
            email_notifications_enabled=email_notifications_enabled,
            marketing_notifications_enabled=marketing_notifications_enabled,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _preferences_entity(row)

    async def update_preferences(
        self,
        *,
        user_id: UUID,
        language: UserLanguage | None,
        theme: UserTheme | None,
        push_notifications_enabled: bool | None,
        email_notifications_enabled: bool | None,
        marketing_notifications_enabled: bool | None,
        now: datetime,
    ) -> UserPreferences | None:
        result = await self._session.execute(
            select(UserPreferencesModel).where(UserPreferencesModel.user_id == user_id),
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        if language is not None:
            row.language = language.value
        if theme is not None:
            row.theme = theme.value
        if push_notifications_enabled is not None:
            row.push_notifications_enabled = push_notifications_enabled
        if email_notifications_enabled is not None:
            row.email_notifications_enabled = email_notifications_enabled
        if marketing_notifications_enabled is not None:
            row.marketing_notifications_enabled = marketing_notifications_enabled
        row.updated_at = now
        await self._session.flush()
        return _preferences_entity(row)
