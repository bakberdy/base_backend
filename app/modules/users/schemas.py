from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}
