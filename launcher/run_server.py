from __future__ import annotations

import os

import uvicorn

from app.core.logging import log_server_start


def main() -> None:
    host = os.environ.get("HOST", os.environ.get("FAB_HOST", "0.0.0.0"))
    port = int(os.environ.get("PORT", os.environ.get("FAB_PORT", "5000")))
    log_server_start()
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
