from __future__ import annotations

import unittest

from fastapi import FastAPI

from fabouanes.fastapi_compat import Flask, jsonify, request, session


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
