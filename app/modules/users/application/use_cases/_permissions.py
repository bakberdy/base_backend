from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole, UserStatus
from app.modules.users.domain.exceptions import ForbiddenUserActionError, UserNotFoundError
from app.modules.users.domain.repositories import UserRepository


async def get_admin_actor(user_repo: UserRepository, actor_id) -> User:
    actor = await user_repo.get_by_id(actor_id)
    if actor is None:
        raise UserNotFoundError()
    if actor.status != UserStatus.ACTIVE:
        raise ForbiddenUserActionError()
    if actor.role not in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        raise ForbiddenUserActionError()
    return actor


def ensure_can_manage_target(actor: User, target: User) -> None:
    if actor.role == UserRole.SUPER_ADMIN:
        return
    if actor.role == UserRole.ADMIN and target.role == UserRole.USER:
        return
    raise ForbiddenUserActionError()
