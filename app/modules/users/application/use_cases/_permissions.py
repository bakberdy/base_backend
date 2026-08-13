from app.modules.users.domain.entities import User
from app.modules.users.domain.enums import UserRole
from app.modules.users.domain.exceptions import ForbiddenUserActionError


def ensure_can_manage_target(actor_role: UserRole, target: User) -> None:
    if actor_role == UserRole.SUPER_ADMIN:
        return
    if actor_role == UserRole.ADMIN and target.role == UserRole.USER:
        return
    raise ForbiddenUserActionError()
