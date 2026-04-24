from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fabouanes.fastapi_compat import Flask, jsonify
from fabouanes.routes.api_v1_routes import _apply_api_cors


class ApiSecurityTests(unittest.TestCase):
    def _build_app(self) -> Flask:
        app = Flask(__name__)
        app.after_request(_apply_api_cors)

        @app.route("/api/v1/ping", methods=["GET", "OPTIONS"])
        def ping():
            return jsonify({"ok": True})

        return app

    def test_cors_rejects_unknown_origin_when_allow_all_is_disabled(self) -> None:
        app = self._build_app()
        client = app.test_client()
        with patch.dict(os.environ, {"CORS_ALLOW_ALL": "0", "CORS_ALLOW_ORIGINS": "http://localhost"}, clear=False):
            response = client.get("/api/v1/ping", headers={"Origin": "http://evil.example"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "null")

    def test_cors_accepts_localhost_origin(self) -> None:
        app = self._build_app()
        client = app.test_client()
        with patch.dict(os.environ, {"CORS_ALLOW_ALL": "0", "CORS_ALLOW_ORIGINS": "http://localhost"}, clear=False):
            response = client.get("/api/v1/ping", headers={"Origin": "http://localhost"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Access-Control-Allow-Origin"), "http://localhost")
