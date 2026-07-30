from __future__ import annotations

import os
from unittest.mock import patch
from app.core.db_helpers.manager import db_manager


def test_sqlalchemy_database_url_termux_unix_formatting():
    with patch.dict(os.environ, {"PREFIX": "/tmp/test_termux_prefix"}):
        res = db_manager.sqlalchemy_database_url("postgresql://postgres:0000@127.0.0.1:5432/fabouanes")
        assert res.startswith("postgresql+pg8000://")

    with patch("os.path.exists", return_value=True):
        res_unix = db_manager.sqlalchemy_database_url("postgresql://admin:7508@localhost:5432/testdb")
        assert "unix_sock" in res_unix or "pg8000" in res_unix
