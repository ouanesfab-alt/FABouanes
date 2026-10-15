import sys
from app.core import database as _db
from app.core.config import settings
import app.web.exception_handlers as _eh

sys.modules.setdefault("app.core.db_helpers", _db)
sys.modules.setdefault("app.core.db_helpers.manager", _db)
sys.modules.setdefault("app.core.db_helpers.execute", _db)
sys.modules.setdefault("app.core.db_helpers.query", _db)
setattr(sys.modules[__name__], "db_helpers", _db)

sys.modules.setdefault("app.core.exception_handlers", _eh)

__all__ = ["settings"]
