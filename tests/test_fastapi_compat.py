from __future__ import annotations

import os
import unittest
import json
from unittest.mock import patch

from fastapi import FastAPI

from fabouanes.fastapi_compat import Flask, jsonify, request, session
from fabouanes.security import security_headers


class FastAPICompatTests(unittest.TestCase):
    def test_flask_compat_app_is_a_fastapi_instance(self) -> None:
        app = Flask(__name__)

        self.assertIsInstance(app, FastAPI)

    def test_test_client_preserves_session_and_request_context(self) -> None:
        app = Flask(__name__)

        @app.route("/session", methods=["GET", "POST"])
        def session_view():
            if request.method == "POST":
                session["user_id"] = 7
                return jsonify({"ok": True, "method": request.method})
            return jsonify({"user_id": session.get("user_id"), "method": request.method})

        client = app.test_client()

        post_response = client.post("/session")
        self.assertEqual(post_response.status_code, 200)
        self.assertEqual(post_response.get_json()["method"], "POST")

        with client.session_transaction() as sess:
            self.assertEqual(sess["user_id"], 7)
            sess["user_id"] = 8

        get_response = client.get("/session")
        payload = get_response.get_json()

        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(payload["user_id"], 8)
        self.assertEqual(payload["method"], "GET")

    def test_reset_routes_keeps_only_requested_endpoints(self) -> None:
        app = Flask(__name__)

        @app.route("/old", methods=["GET"])
        def old_route():
            return jsonify({"ok": True})

        app.reset_routes({"static"})

        self.assertNotIn("old_route", app.view_functions)
        self.assertFalse(any(rule.endpoint == "old_route" for rule in app.url_map.iter_rules()))

    def test_swagger_docs_are_enabled_by_default(self) -> None:
        app = Flask(__name__)
        client = app.test_client()

        docs_response = client.get("/api/docs")
        openapi_response = client.get("/api/openapi.json")

        self.assertEqual(docs_response.status_code, 200)
        self.assertEqual(openapi_response.status_code, 200)

    def test_swagger_docs_can_be_disabled_from_env(self) -> None:
        with patch.dict(os.environ, {"API_DOCS_ENABLED": "0"}):
            app = Flask(__name__)
            client = app.test_client()
            docs_response = client.get("/api/docs")
            self.assertEqual(docs_response.status_code, 404)

    def test_unhandled_api_exception_returns_json_error_with_request_id(self) -> None:
        app = Flask(__name__)

        @app.route("/api/v1/crash", methods=["GET"])
        def crash():
            raise RuntimeError("boom")

        client = app.test_client()
        response = client.get("/api/v1/crash")
        payload = response.get_json()

        self.assertEqual(response.status_code, 500)
        self.assertEqual(payload["error"]["code"], "internal_error")
        self.assertTrue(response.headers.get("X-Request-ID"))
        self.assertEqual(payload["error"]["request_id"], response.headers.get("X-Request-ID"))

    def test_request_logs_are_structured_json(self) -> None:
        app = Flask(__name__)

        @app.route("/ping", methods=["GET"])
        def ping():
            return jsonify({"ok": True})

        client = app.test_client()
        app.logger.setLevel("INFO")
        with self.assertLogs(app.logger, level="INFO") as logs:
            response = client.get("/ping")
        self.assertEqual(response.status_code, 200)
        found = False
        for line in logs.output:
            parts = line.split(":", 2)
            message = parts[2] if len(parts) >= 3 else line
            try:
                payload = json.loads(message)
            except Exception:
                continue
            if payload.get("event") == "http_request":
                found = True
                self.assertEqual(payload.get("path"), "/ping")
                self.assertEqual(payload.get("status_code"), 200)
                break
        self.assertTrue(found)

    def test_security_headers_apply_on_api_routes(self) -> None:
        app = Flask(__name__)
        app.after_request(security_headers)

        @app.route("/api/v1/headers", methods=["GET"])
        def api_headers():
            return jsonify({"ok": True})

        client = app.test_client()
        response = client.get("/api/v1/headers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
