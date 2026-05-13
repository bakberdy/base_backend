import importlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def apply_postgresql_schema_patches(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32)"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS status VARCHAR(32)"))
        await conn.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL"))
        await conn.execute(text("UPDATE users SET status = 'active' WHERE status IS NULL"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'user'"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN status SET DEFAULT 'active'"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN role SET NOT NULL"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN status SET NOT NULL"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_status ON users (status)"))


def load_model_metadata() -> None:
    importlib.import_module("app.db.models_registry")
