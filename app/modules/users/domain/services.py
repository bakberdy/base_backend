from typing import Protocol


class AvatarStorageService(Protocol):
    async def save_avatar(
        self,
        *,
        user_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> tuple[str, str]: ...

    async def delete_avatar(self, *, object_key: str) -> None: ...


class UserPermissionService(Protocol):
    pass
