import importlib

from sqlalchemy.ext.asyncio import AsyncEngine


async def apply_postgresql_schema_patches(engine: AsyncEngine) -> None:
    return


def load_model_metadata() -> None:
    importlib.import_module("app.db.models_registry")
