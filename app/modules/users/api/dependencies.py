from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SqlAlchemyUnitOfWork, get_db
from app.modules.users.application.use_cases.change_user_role import ChangeUserRoleUseCase
from app.modules.users.application.use_cases.change_user_status import ChangeUserStatusUseCase
from app.modules.users.application.use_cases.get_current_user import GetCurrentUserUseCase
from app.modules.users.application.use_cases.get_user_by_id import GetUserByIdUseCase
from app.modules.users.application.use_cases.get_users import GetUsersUseCase
from app.modules.users.domain.repositories import UserRepository
from app.modules.users.infrastructure.sqlalchemy_repositories import SqlAlchemyUserRepository


def get_user_repository(session: AsyncSession = Depends(get_db)) -> UserRepository:
    return SqlAlchemyUserRepository(session)


def get_users_use_case(repo: UserRepository = Depends(get_user_repository)) -> GetUsersUseCase:
    return GetUsersUseCase(repo)


def get_user_by_id_use_case(repo: UserRepository = Depends(get_user_repository)) -> GetUserByIdUseCase:
    return GetUserByIdUseCase(repo)


def get_current_user_use_case(repo: UserRepository = Depends(get_user_repository)) -> GetCurrentUserUseCase:
    return GetCurrentUserUseCase(repo)


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


GetUsersUseCaseDep = Annotated[GetUsersUseCase, Depends(get_users_use_case)]
GetUserByIdUseCaseDep = Annotated[GetUserByIdUseCase, Depends(get_user_by_id_use_case)]
GetCurrentUserUseCaseDep = Annotated[GetCurrentUserUseCase, Depends(get_current_user_use_case)]
ChangeUserRoleUseCaseDep = Annotated[ChangeUserRoleUseCase, Depends(change_user_role_use_case)]
ChangeUserStatusUseCaseDep = Annotated[ChangeUserStatusUseCase, Depends(change_user_status_use_case)]
