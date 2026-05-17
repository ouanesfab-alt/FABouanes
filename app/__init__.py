from app.main import app
from app.core.database import bootstrap_and_migrate
from app.core.runtime_paths import ensure_runtime_dirs
from app.core.logging import log_server_start

# Alias for backward compatibility
init_db = bootstrap_and_migrate

__all__ = ["app", "bootstrap_and_migrate", "init_db", "ensure_runtime_dirs", "log_server_start"]
