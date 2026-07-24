from typing import Annotated
from uuid import UUID

from fastapi import Depends

CurrentUserId = Annotated[UUID, Depends()]
