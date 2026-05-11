"""Import feature models so :meth:`Base.metadata.create_all` sees every table."""

from app.modules.auth.models import LoginRequest, UserDevice, UserSession  # noqa: F401
from app.modules.users.models import User  # noqa: F401
