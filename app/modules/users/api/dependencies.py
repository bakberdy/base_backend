from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SqlAlchemyUnitOfWork, get_db
from app.modules.auth.domain.repositories import AuthRepository
from app.modules.auth.infrastructure.sqlalchemy_repositories import SqlAlchemyAuthRepository
from app.modules.users.application.use_cases.approve_user_deletion_request import (
    ApproveUserDeletionRequestUseCase,
)
from app.modules.users.application.use_cases.change_user_role import ChangeUserRoleUseCase
from app.modules.users.application.use_cases.change_user_status import ChangeUserStatusUseCase
from app.modules.users.application.use_cases.create_user_preferences import (
    CreateUserPreferencesUseCase,
)
from app.modules.users.application.use_cases.create_user_profile import CreateUserProfileUseCase
from app.modules.users.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.modules.users.application.use_cases.get_current_user_profile import (
    GetCurrentUserProfileUseCase,
)
from app.modules.users.application.use_cases.get_user_by_id import GetUserByIdUseCase
from app.modules.users.application.use_cases.get_user_preferences import GetUserPreferencesUseCase
from app.modules.users.application.use_cases.get_user_profile_by_id import GetUserProfileByIdUseCase
from app.modules.users.application.use_cases.get_users import GetUsersUseCase
from app.modules.users.application.use_cases.remove_user_avatar import RemoveUserAvatarUseCase
from app.modules.users.application.use_cases.request_account_deletion import (
    RequestAccountDeletionUseCase,
)
from app.modules.users.application.use_cases.update_user_avatar import UpdateUserAvatarUseCase
from app.modules.users.application.use_cases.update_user_preferences import (
    UpdateUserPreferencesUseCase,
)
from app.modules.users.application.use_cases.update_user_profile import UpdateUserProfileUseCase
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.domain.services import AvatarStorageService
from app.modules.users.infrastructure.local_avatar_storage import LocalAvatarStorageService
from app.modules.users.infrastructure.sqlalchemy_repositories import SqlAlchemyUserRepository


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_auth_repository(session: AsyncSession = Depends(get_db)) -> AuthRepository:
    return SqlAlchemyAuthRepository(session)


def get_avatar_storage() -> AvatarStorageService:
    return LocalAvatarStorageService()


def get_users_use_case(repo: UserRepository = Depends(get_user_repository)) -> GetUsersUseCase:
    return GetUsersUseCase(repo)


def get_user_by_id_use_case(
    repo: UserRepository = Depends(get_user_repository),
) -> GetUserByIdUseCase:
    return GetUserByIdUseCase(repo)


def get_user_profile_by_id_use_case(
    repo: UserRepository = Depends(get_user_repository),
) -> GetUserProfileByIdUseCase:
    return GetUserProfileByIdUseCase(repo)


def get_current_user_use_case(
    repo: UserRepository = Depends(get_user_repository),
) -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(repo)


def get_current_user_profile_use_case(
    repo: UserRepository = Depends(get_user_repository),
) -> GetCurrentUserProfileUseCase:
    return GetCurrentUserProfileUseCase(repo)


def change_user_role_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> ChangeUserRoleUseCase:
    return ChangeUserRoleUseCase(repo, SqlAlchemyUnitOfWork(session))


def change_user_status_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> ChangeUserStatusUseCase:
    return ChangeUserStatusUseCase(repo, SqlAlchemyUnitOfWork(session))


def create_user_profile_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> CreateUserProfileUseCase:
    return CreateUserProfileUseCase(repo, SqlAlchemyUnitOfWork(session))


def update_user_profile_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> UpdateUserProfileUseCase:
    return UpdateUserProfileUseCase(repo, SqlAlchemyUnitOfWork(session))


def update_user_avatar_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
    storage: AvatarStorageService = Depends(get_avatar_storage),
) -> UpdateUserAvatarUseCase:
    return UpdateUserAvatarUseCase(repo, storage, SqlAlchemyUnitOfWork(session))


def remove_user_avatar_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
    storage: AvatarStorageService = Depends(get_avatar_storage),
) -> RemoveUserAvatarUseCase:
    return RemoveUserAvatarUseCase(repo, storage, SqlAlchemyUnitOfWork(session))


def get_user_preferences_use_case(
    repo: UserRepository = Depends(get_user_repository),
) -> GetUserPreferencesUseCase:
    return GetUserPreferencesUseCase(repo)


def create_user_preferences_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> CreateUserPreferencesUseCase:
    return CreateUserPreferencesUseCase(repo, SqlAlchemyUnitOfWork(session))


def update_user_preferences_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> UpdateUserPreferencesUseCase:
    return UpdateUserPreferencesUseCase(repo, SqlAlchemyUnitOfWork(session))


def request_account_deletion_use_case(
    session: AsyncSession = Depends(get_db),
    repo: UserRepository = Depends(get_user_repository),
) -> RequestAccountDeletionUseCase:
    return RequestAccountDeletionUseCase(repo, SqlAlchemyUnitOfWork(session))


def approve_user_deletion_request_use_case(
    session: AsyncSession = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_repo: AuthRepository = Depends(get_auth_repository),
) -> ApproveUserDeletionRequestUseCase:
    return ApproveUserDeletionRequestUseCase(user_repo, auth_repo, SqlAlchemyUnitOfWork(session))


GetUsersUseCaseDep = Annotated[GetUsersUseCase, Depends(get_users_use_case)]
GetUserByIdUseCaseDep = Annotated[GetUserByIdUseCase, Depends(get_user_by_id_use_case)]
GetUserProfileByIdUseCaseDep = Annotated[
    GetUserProfileByIdUseCase,
    Depends(get_user_profile_by_id_use_case),
]
GetCurrentUserUseCaseDep = Annotated[GetCurrentUserUseCase, Depends(get_current_user_use_case)]
GetCurrentUserProfileUseCaseDep = Annotated[
    GetCurrentUserProfileUseCase,
    Depends(get_current_user_profile_use_case),
]
ChangeUserRoleUseCaseDep = Annotated[ChangeUserRoleUseCase, Depends(change_user_role_use_case)]
ChangeUserStatusUseCaseDep = Annotated[
    ChangeUserStatusUseCase, Depends(change_user_status_use_case)
]
CreateUserProfileUseCaseDep = Annotated[
    CreateUserProfileUseCase, Depends(create_user_profile_use_case)
]
UpdateUserProfileUseCaseDep = Annotated[
    UpdateUserProfileUseCase, Depends(update_user_profile_use_case)
]
UpdateUserAvatarUseCaseDep = Annotated[
    UpdateUserAvatarUseCase, Depends(update_user_avatar_use_case)
]
RemoveUserAvatarUseCaseDep = Annotated[
    RemoveUserAvatarUseCase, Depends(remove_user_avatar_use_case)
]
GetUserPreferencesUseCaseDep = Annotated[
    GetUserPreferencesUseCase, Depends(get_user_preferences_use_case)
]
CreateUserPreferencesUseCaseDep = Annotated[
    CreateUserPreferencesUseCase, Depends(create_user_preferences_use_case)
]
UpdateUserPreferencesUseCaseDep = Annotated[
    UpdateUserPreferencesUseCase, Depends(update_user_preferences_use_case)
]
RequestAccountDeletionUseCaseDep = Annotated[
    RequestAccountDeletionUseCase, Depends(request_account_deletion_use_case)
]
ApproveUserDeletionRequestUseCaseDep = Annotated[
    ApproveUserDeletionRequestUseCase,
    Depends(approve_user_deletion_request_use_case),
]
