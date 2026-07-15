# Backward compatibility shim — re-exports all public symbols from infrastructure layer
from app.modules.users.infrastructure.repository import *  # noqa: F401, F403
from app.modules.users.infrastructure.repository import UserRepository  # noqa: F401
