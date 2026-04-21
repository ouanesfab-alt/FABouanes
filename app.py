from fabouanes.app_factory import create_app
from fabouanes.runtime_app import ensure_runtime_dirs, init_db, log_server_start
import os

app = create_app()

__all__ = ["app", "ensure_runtime_dirs", "init_db", "log_server_start"]

if __name__ == "__main__":
    log_server_start()
    host = os.environ.get("FAB_HOST", "0.0.0.0")
    port = int(os.environ.get("FAB_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
