from fastapi import APIRouter, status

from app.modules.auth.deps import CurrentUserIdDep
from app.modules.users.deps import UserRepositoryDep
from app.modules.users.schemas import UserOut
from app.schemas.error import api_http_exception

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def users_me(user_id: CurrentUserIdDep, repo: UserRepositoryDep) -> UserOut:
    user = await repo.get_by_id(user_id)
    if user is None:
        raise api_http_exception(
            status.HTTP_404_NOT_FOUND,
            "User not found",
        )
    return UserOut.model_validate(user)
