from pathlib import Path
from uuid import uuid4


class LocalAvatarStorageService:
    def __init__(self, base_dir: Path | None = None, public_prefix: str = "/uploads/avatars") -> None:
        self._base_dir = base_dir or Path("uploads") / "avatars"
        self._public_prefix = public_prefix.rstrip("/")

    async def save_avatar(
        self,
        *,
        user_id: str,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> tuple[str, str]:
        extension = _avatar_extension(content_type, filename)
        object_key = f"{user_id}/{uuid4().hex}{extension}"
        path = self._base_dir / object_key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return f"{self._public_prefix}/{object_key}", object_key

    async def delete_avatar(self, *, object_key: str) -> None:
        path = self._base_dir / object_key
        if path.exists():
            path.unlink()


def _avatar_extension(content_type: str, filename: str) -> str:
    by_content_type = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    if content_type in by_content_type:
        return by_content_type[content_type]
    suffix = Path(filename).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".bin"
