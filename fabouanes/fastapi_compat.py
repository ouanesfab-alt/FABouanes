from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import anyio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from itsdangerous import BadData, URLSafeSerializer
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.datastructures import UploadFile
from starlette.requests import Request as StarletteRequest
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from werkzeug.datastructures import FileStorage, MultiDict
from werkzeug.exceptions import Aborter, HTTPException as WerkzeugHTTPException, NotFound
from werkzeug.local import LocalProxy

_aborter = Aborter()
_request_var: ContextVar["RequestCompat | None"] = ContextVar("fab_request", default=None)
_session_var: ContextVar["SessionDict | None"] = ContextVar("fab_session", default=None)
_g_var: ContextVar["GState | None"] = ContextVar("fab_g", default=None)
_app_var: ContextVar["Flask | None"] = ContextVar("fab_app", default=None)

_RULE_PATTERN = re.compile(r"<(?:(?P<converter>[^:<>]+):)?(?P<name>[^<>]+)>")
_CONVERTER_MAP = {
    "int": "int",
    "float": "float",
    "path": "path",
    "string": "",
}


def _require_context(value: Any, name: str) -> Any:
    if value is None:
        raise RuntimeError(f"Working outside of {name} context.")
    return value


def _get_request() -> "RequestCompat":
    return _require_context(_request_var.get(), "request")


def _get_session() -> "SessionDict":
    return _require_context(_session_var.get(), "session")


def _get_g() -> "GState":
    return _require_context(_g_var.get(), "application")


def _get_current_app() -> "Flask":
    return _require_context(_app_var.get(), "application")


request = LocalProxy(_get_request)
session = LocalProxy(_get_session)
g = LocalProxy(_get_g)
current_app = LocalProxy(_get_current_app)


class GState:
    def __init__(self) -> None:
        object.__setattr__(self, "_data", {})

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value: Any) -> None:
        self._data[name] = value

    def __delattr__(self, name: str) -> None:
        self._data.pop(name, None)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def pop(self, key: str, default: Any = None) -> Any:
        return self._data.pop(key, default)

    def __contains__(self, item: object) -> bool:
        return item in self._data


class SessionDict(dict):
    def __init__(self, *args: Any, permanent: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.modified = False
        self.permanent = bool(permanent)

    def _mark_modified(self) -> None:
        self.modified = True

    def __setitem__(self, key: Any, value: Any) -> None:
        self._mark_modified()
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self._mark_modified()
        super().__delitem__(key)

    def clear(self) -> None:
        self._mark_modified()
        self.permanent = False
        super().clear()

    def pop(self, key: Any, default: Any = None) -> Any:
        self._mark_modified()
        return super().pop(key, default)

    def popitem(self) -> tuple[Any, Any]:
        self._mark_modified()
        return super().popitem()

    def setdefault(self, key: Any, default: Any = None) -> Any:
        if key not in self:
            self._mark_modified()
        return super().setdefault(key, default)

    def update(self, *args: Any, **kwargs: Any) -> None:
        if args or kwargs:
            self._mark_modified()
        super().update(*args, **kwargs)


class RequestCompat:
    def __init__(self, starlette_request: StarletteRequest, endpoint: str) -> None:
        self._request = starlette_request
        self.endpoint = endpoint
        self.args = MultiDict(list(starlette_request.query_params.multi_items()))
        self._form: MultiDict | None = None
        self._files: MultiDict | None = None
        self._json_loaded = False
        self._json_payload: Any = None

    @property
    def method(self) -> str:
        return self._request.method.upper()

    @property
    def path(self) -> str:
        return self._request.url.path

    @property
    def headers(self):
        return self._request.headers

    @property
    def remote_addr(self) -> str:
        client = self._request.client
        return client.host if client is not None and client.host else ""

    @property
    def url(self) -> str:
        return str(self._request.url)

    @property
    def host(self) -> str:
        return self._request.headers.get("host", "")

    @property
    def scheme(self) -> str:
        return self._request.url.scheme

    @property
    def is_json(self) -> bool:
        content_type = (self._request.headers.get("content-type", "") or "").lower()
        return "application/json" in content_type

    @property
    def state(self):
        return self._request.state

    @property
    def form(self) -> MultiDict:
        if self._form is None:
            self._load_form_data()
        return self._form or MultiDict()

    @property
    def files(self) -> MultiDict:
        if self._files is None:
            self._load_form_data()
        return self._files or MultiDict()

    def _load_form_data(self) -> None:
        form_data = anyio.from_thread.run(self._request.form)
        form_items: list[tuple[str, Any]] = []
        file_items: list[tuple[str, FileStorage]] = []
        for key, value in form_data.multi_items():
            if isinstance(value, UploadFile):
                try:
                    value.file.seek(0)
                except Exception:
                    pass
                file_items.append(
                    (
                        key,
                        FileStorage(
                            stream=value.file,
                            filename=value.filename or "",
                            name=key,
                            content_type=value.content_type or "application/octet-stream",
                        ),
                    )
                )
            else:
                form_items.append((key, value))
        self._form = MultiDict(form_items)
        self._files = MultiDict(file_items)

    def get_json(self, silent: bool = False) -> Any:
        if self._json_loaded:
            return self._json_payload
        self._json_loaded = True
        if not self.is_json:
            self._json_payload = None
            return None
        try:
            self._json_payload = anyio.from_thread.run(self._request.json)
        except Exception:
            if not silent:
                raise
            self._json_payload = None
        return self._json_payload

    def __getattr__(self, name: str) -> Any:
        return getattr(self._request, name)


@dataclass(frozen=True)
class RuleInfo:
    rule: str
    endpoint: str
    methods: set[str]


class UrlMapCompat:
    def __init__(self) -> None:
        self._rules: list[RuleInfo] = []

    def add_rule(self, rule: str, endpoint: str, methods: set[str]) -> None:
        for existing in self._rules:
            if existing.rule == rule and existing.endpoint == endpoint and existing.methods == methods:
                return
        self._rules.append(RuleInfo(rule=rule, endpoint=endpoint, methods=methods))

    def iter_rules(self):
        return list(self._rules)


class Flask(FastAPI):
    def __init__(self, import_name: str, template_folder: str | None = None, static_folder: str | None = None) -> None:
        docs_enabled = (str(os.environ.get("API_DOCS_ENABLED", "1")) or "").strip().lower() not in {
            "",
            "0",
            "false",
            "no",
            "off",
        }
        docs_url = (os.environ.get("API_DOCS_PATH", "/api/docs") or "").strip() or "/api/docs"
        redoc_url = (os.environ.get("API_REDOC_PATH", "/api/redoc") or "").strip() or "/api/redoc"
        openapi_url = (os.environ.get("API_OPENAPI_PATH", "/api/openapi.json") or "").strip() or "/api/openapi.json"
        super().__init__(
            docs_url=docs_url if docs_enabled else None,
            redoc_url=redoc_url if docs_enabled else None,
            openapi_url=openapi_url if docs_enabled else None,
        )
        self.import_name = import_name
        self.config: dict[str, Any] = {}
        self.view_functions: dict[str, Any] = {}
        self.url_map = UrlMapCompat()
        self._before_request_funcs: list[Any] = []
        self._after_request_funcs: list[Any] = []
        self._teardown_funcs: list[Any] = []
        self._context_processors: list[Any] = []
        self._error_handlers: dict[type[Any], Any] = {}
        self.session_cookie_name = "session"
        self.template_folder = Path(template_folder or "templates")
        self.static_folder = Path(static_folder or "static")
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_folder)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.logger = logging.getLogger(import_name)
        self.wsgi_app = self
        self.jinja_env.globals.update(
            url_for=url_for,
            get_flashed_messages=get_flashed_messages,
            request=request,
            session=session,
            g=g,
        )
        if self.static_folder.exists():
            self.mount("/static", StaticFiles(directory=str(self.static_folder)), name="static")
            self.url_map.add_rule("/static/<path:filename>", "static", {"GET"})

    def route(self, rule: str, methods: list[str] | None = None, endpoint: str | None = None):
        def decorator(view_func):
            self.add_url_rule(rule, endpoint=endpoint or view_func.__name__, view_func=view_func, methods=methods or ["GET"])
            return view_func

        return decorator

    def get(self, rule: str, endpoint: str | None = None):
        return self.route(rule, methods=["GET"], endpoint=endpoint)

    def post(self, rule: str, endpoint: str | None = None):
        return self.route(rule, methods=["POST"], endpoint=endpoint)

    def add_url_rule(self, rule: str, endpoint: str | None = None, view_func=None, methods: list[str] | None = None) -> None:
        endpoint_name = endpoint or getattr(view_func, "__name__", "")
        if not endpoint_name:
            raise ValueError("endpoint name is required")
        if view_func is None:
            raise ValueError("view_func is required")
        route_methods = [method.upper() for method in (methods or ["GET"])]
        exposed_methods = list(route_methods)
        if "OPTIONS" not in exposed_methods:
            exposed_methods.append("OPTIONS")
        if endpoint_name in self.view_functions:
            self.view_functions[endpoint_name] = view_func
            return
        self.view_functions[endpoint_name] = view_func
        self.url_map.add_rule(rule, endpoint_name, set(exposed_methods))
        converted_rule = _convert_rule(rule)

        def endpoint_handler(starlette_request: StarletteRequest) -> Response:
            if starlette_request.method.upper() == "OPTIONS":
                return self._dispatch_options_response(endpoint_name, starlette_request)
            return self._dispatch_request(endpoint_name, starlette_request)

        self.router.add_route(converted_rule, endpoint_handler, methods=exposed_methods, name=endpoint_name)

    def before_request(self, func):
        self._before_request_funcs.append(func)
        return func

    def after_request(self, func):
        self._after_request_funcs.append(func)
        return func

    def teardown_appcontext(self, func):
        self._teardown_funcs.append(func)
        return func

    def context_processor(self, func):
        self._context_processors.append(func)
        return func

    def errorhandler(self, exception_class: type[Any]):
        def decorator(func):
            self._error_handlers[exception_class] = func
            return func

        return decorator

    @contextmanager
    def app_context(self):
        token_app = _app_var.set(self)
        token_g = _g_var.set(GState())
        try:
            yield self
        finally:
            exc: Exception | None = None
            for hook in self._teardown_funcs:
                try:
                    hook(exc)
                except Exception:
                    self.logger.exception("App teardown hook failed")
            _g_var.reset(token_g)
            _app_var.reset(token_app)

    def run(self, host: str = "127.0.0.1", port: int = 8000, debug: bool = False) -> None:
        import uvicorn

        uvicorn.run(self, host=host, port=port, log_level="debug" if debug else "info")

    def test_client(self):
        return FastAPITestClient(self)

    def reset_routes(self, keep_endpoints: set[str] | None = None) -> None:
        keep = set(keep_endpoints or {"static"})
        self.view_functions = {name: func for name, func in self.view_functions.items() if name in keep}
        self.url_map = UrlMapCompat()
        self.router.routes = [route for route in self.router.routes if isinstance(route, Mount) or getattr(route, "name", None) in keep]
        for route in self.router.routes:
            if getattr(route, "name", None) in keep:
                path = getattr(route, "path", None)
                methods = set(getattr(route, "methods", {"GET"}))
                if path:
                    self.url_map.add_rule(path, str(route.name), methods)

    def _session_serializer(self) -> URLSafeSerializer:
        secret = str(self.config.get("SECRET_KEY") or "fabouanes-dev-secret")
        return URLSafeSerializer(secret, salt="fabouanes-session")

    def _load_session(self, starlette_request: StarletteRequest) -> SessionDict:
        raw_value = starlette_request.cookies.get(self.session_cookie_name, "")
        if not raw_value:
            return SessionDict()
        try:
            payload = self._session_serializer().loads(raw_value)
        except BadData:
            return SessionDict()
        if not isinstance(payload, dict):
            return SessionDict()
        permanent = bool(payload.pop("_permanent", False))
        return SessionDict(payload, permanent=permanent)

    def _save_session(self, response: Response, starlette_request: StarletteRequest, session_state: SessionDict) -> None:
        should_delete = not session_state and (session_state.modified or starlette_request.cookies.get(self.session_cookie_name))
        if should_delete:
            response.delete_cookie(self.session_cookie_name, path="/")
            return
        if not session_state.modified and not starlette_request.cookies.get(self.session_cookie_name):
            return
        payload = dict(session_state)
        if session_state.permanent:
            payload["_permanent"] = True
        signed = self._session_serializer().dumps(payload)
        max_age = None
        if session_state.permanent:
            max_age = int(self.config.get("PERMANENT_SESSION_LIFETIME", 0) or 0) or None
        response.set_cookie(
            self.session_cookie_name,
            signed,
            path="/",
            httponly=bool(self.config.get("SESSION_COOKIE_HTTPONLY", True)),
            samesite=str(self.config.get("SESSION_COOKIE_SAMESITE", "lax")),
            secure=bool(self.config.get("SESSION_COOKIE_SECURE", False)),
            max_age=max_age,
        )

    def _dispatch_request(self, endpoint: str, starlette_request: StarletteRequest) -> Response:
        compat_request = RequestCompat(starlette_request, endpoint)
        request_id = str(starlette_request.headers.get("X-Request-ID", "") or "").strip() or secrets.token_hex(8)
        setattr(compat_request, "request_id", request_id)
        session_state = self._load_session(starlette_request)
        token_app = _app_var.set(self)
        token_request = _request_var.set(compat_request)
        token_session = _session_var.set(session_state)
        token_g = _g_var.set(GState())
        response: Response | None = None
        caught_exc: Exception | None = None
        started_at = time.perf_counter()
        try:
            try:
                result: Any = None
                for hook in self._before_request_funcs:
                    interim = hook()
                    if interim is not None:
                        result = interim
                        break
                if result is None:
                    view_func = self.view_functions[endpoint]
                    result = view_func(**starlette_request.path_params)
                response = self._make_response(result)
            except Exception as exc:  # pragma: no cover - covered by higher-level tests
                caught_exc = exc
                response = self._handle_exception(exc)
            finalized = self._finalize_response(response, starlette_request, session_state)
            elapsed_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
            try:
                self.logger.info(
                    json.dumps(
                        {
                            "event": "http_request",
                            "request_id": request_id,
                            "method": compat_request.method,
                            "path": compat_request.path,
                            "status_code": int(getattr(finalized, "status_code", 0) or 0),
                            "duration_ms": elapsed_ms,
                            "client_ip": compat_request.remote_addr,
                        },
                        ensure_ascii=False,
                    )
                )
            except Exception:
                pass
            return finalized
        finally:
            for hook in self._teardown_funcs:
                try:
                    hook(caught_exc)
                except Exception:
                    self.logger.exception("Request teardown hook failed")
            _g_var.reset(token_g)
            _session_var.reset(token_session)
            _request_var.reset(token_request)
            _app_var.reset(token_app)

    def _dispatch_options_response(self, endpoint: str, starlette_request: StarletteRequest) -> Response:
        compat_request = RequestCompat(starlette_request, endpoint)
        session_state = self._load_session(starlette_request)
        token_app = _app_var.set(self)
        token_request = _request_var.set(compat_request)
        token_session = _session_var.set(session_state)
        token_g = _g_var.set(GState())
        try:
            return self._finalize_response(Response(status_code=200), starlette_request, session_state)
        finally:
            _g_var.reset(token_g)
            _session_var.reset(token_session)
            _request_var.reset(token_request)
            _app_var.reset(token_app)

    def _finalize_response(self, response: Response, starlette_request: StarletteRequest, session_state: SessionDict) -> Response:
        for hook in self._after_request_funcs:
            updated = hook(response)
            if updated is not None:
                response = updated
        request_state = _request_var.get()
        request_id = getattr(request_state, "request_id", "")
        if request_id:
            response.headers.setdefault("X-Request-ID", str(request_id))
        self._save_session(response, starlette_request, session_state)
        return response

    def _handle_exception(self, exc: Exception) -> Response:
        for exc_type in type(exc).mro():
            handler = self._error_handlers.get(exc_type)
            if handler is not None:
                return self._make_response(handler(exc))
        if isinstance(exc, WerkzeugHTTPException):
            return self._make_response(exc)
        try:
            request_state = _request_var.get()
            path = str(getattr(request_state, "path", "") or "")
            request_id = str(getattr(request_state, "request_id", "") or "")
            self.logger.exception(
                json.dumps(
                    {
                        "event": "http_exception",
                        "request_id": request_id,
                        "path": path,
                        "exception_type": type(exc).__name__,
                        "message": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            if path.startswith("/api/"):
                return JSONResponse(
                    {"error": {"code": "internal_error", "message": "Erreur interne.", "request_id": request_id}},
                    status_code=500,
                )
        except Exception:
            pass
        raise exc

    def _make_response(self, value: Any) -> Response:
        status_code: int | None = None
        headers: dict[str, Any] | None = None
        body = value
        if isinstance(value, tuple):
            if len(value) == 2:
                body, status_code = value
            elif len(value) == 3:
                body, status_code, headers = value
            else:
                raise TypeError("Unsupported response tuple")
        if isinstance(body, Response):
            response = body
            if status_code is not None:
                response.status_code = status_code
        elif isinstance(body, WerkzeugHTTPException):
            response = PlainTextResponse(body.description or body.name, status_code=body.code or status_code or 500)
        elif isinstance(body, (dict, list, int, float, bool)):
            response = JSONResponse(body, status_code=status_code or 200)
        elif body is None:
            response = Response(status_code=status_code or 204)
        elif isinstance(body, bytes):
            response = Response(body, status_code=status_code or 200, media_type="application/octet-stream")
        else:
            response = HTMLResponse(str(body), status_code=status_code or 200)
        if headers:
            for key, header_value in headers.items():
                response.headers[key] = str(header_value)
        return response


class TestResponseWrapper:
    def __init__(self, response) -> None:
        self._response = response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def headers(self):
        return self._response.headers

    @property
    def mimetype(self) -> str | None:
        content_type = self._response.headers.get("content-type", "")
        if not content_type:
            return None
        return str(content_type).split(";", 1)[0].strip() or None

    @property
    def location(self) -> str | None:
        return self._response.headers.get("location")

    @property
    def request(self):
        return self._response.request

    @property
    def data(self) -> bytes:
        return self._response.content

    def get_data(self, as_text: bool = False):
        return self._response.text if as_text else self._response.content

    def get_json(self):
        return self._response.json()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._response, name)


class _SessionTransaction:
    def __init__(self, client: "FastAPITestClient") -> None:
        self.client = client
        self.session_state = client._load_session_cookie()

    def __enter__(self) -> SessionDict:
        return self.session_state

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.client._save_session_cookie(self.session_state)


class FastAPITestClient:
    def __init__(self, app: Flask) -> None:
        self.app = app
        self._client = TestClient(app)

    def _wrap(self, response) -> TestResponseWrapper:
        return TestResponseWrapper(response)

    def _matching_session_cookies(self):
        jar = getattr(self._client.cookies, "jar", None)
        if jar is None:
            return []
        return [cookie for cookie in jar if cookie.name == self.app.session_cookie_name]

    def _load_session_cookie(self) -> SessionDict:
        matching = self._matching_session_cookies()
        raw_value = matching[-1].value if matching else ""
        if not raw_value:
            try:
                raw_value = self._client.cookies.get(self.app.session_cookie_name, "")
            except Exception:
                raw_value = ""
        if not raw_value:
            return SessionDict()
        try:
            payload = self.app._session_serializer().loads(raw_value)
        except BadData:
            return SessionDict()
        permanent = bool(payload.pop("_permanent", False)) if isinstance(payload, dict) else False
        return SessionDict(payload if isinstance(payload, dict) else {}, permanent=permanent)

    def _clear_session_cookies(self) -> None:
        jar = getattr(self._client.cookies, "jar", None)
        if jar is None:
            self._client.cookies.pop(self.app.session_cookie_name, None)
            return
        targets = [(cookie.domain, cookie.path, cookie.name) for cookie in self._matching_session_cookies()]
        for domain, path, name in targets:
            try:
                jar.clear(domain, path, name)
            except Exception:
                pass
        try:
            self._client.cookies.pop(self.app.session_cookie_name, None)
        except Exception:
            pass

    def _save_session_cookie(self, session_state: SessionDict) -> None:
        matching = self._matching_session_cookies()
        domain = matching[-1].domain if matching else None
        path = matching[-1].path if matching else "/"
        self._clear_session_cookies()
        if not session_state:
            return
        payload = dict(session_state)
        if session_state.permanent:
            payload["_permanent"] = True
        signed = self.app._session_serializer().dumps(payload)
        if domain:
            self._client.cookies.set(self.app.session_cookie_name, signed, domain=domain, path=path)
        else:
            self._client.cookies.set(self.app.session_cookie_name, signed, path=path)

    def session_transaction(self) -> _SessionTransaction:
        return _SessionTransaction(self)

    def open(self, url: str, method: str = "GET", **kwargs: Any) -> TestResponseWrapper:
        return self._wrap(self._client.request(method, url, **kwargs))

    def get(self, url: str, **kwargs: Any) -> TestResponseWrapper:
        return self._wrap(self._client.get(url, **kwargs))

    def post(self, url: str, **kwargs: Any) -> TestResponseWrapper:
        return self._wrap(self._client.post(url, **kwargs))

    def put(self, url: str, **kwargs: Any) -> TestResponseWrapper:
        return self._wrap(self._client.put(url, **kwargs))

    def delete(self, url: str, **kwargs: Any) -> TestResponseWrapper:
        return self._wrap(self._client.delete(url, **kwargs))

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._client.__exit__(exc_type, exc, tb)


def _convert_rule(rule: str) -> str:
    def replace(match: re.Match[str]) -> str:
        converter = (match.group("converter") or "").strip().lower()
        name = match.group("name").strip()
        mapped = _CONVERTER_MAP.get(converter, "")
        if mapped:
            return "{" + f"{name}:{mapped}" + "}"
        return "{" + name + "}"

    return _RULE_PATTERN.sub(replace, rule)


def has_request_context() -> bool:
    return _request_var.get() is not None


def abort(code: int, description: str | None = None):
    raise _aborter(code, description=description)


def flash(message: str, category: str = "message") -> None:
    flashes = list(session.get("_flashes", []))
    flashes.append((category, message))
    session["_flashes"] = flashes


def get_flashed_messages(with_categories: bool = False, category_filter: list[str] | tuple[str, ...] = ()):
    flashes = list(session.pop("_flashes", []))
    if category_filter:
        allowed = set(category_filter)
        flashes = [item for item in flashes if item[0] in allowed]
    if with_categories:
        return flashes
    return [message for _, message in flashes]


def jsonify(*args: Any, **kwargs: Any) -> JSONResponse:
    if args and kwargs:
        raise TypeError("jsonify accepts args or kwargs, not both")
    if kwargs:
        payload: Any = kwargs
    elif len(args) == 1:
        payload = args[0]
    else:
        payload = list(args)
    return JSONResponse(payload)


def redirect(location: str, code: int = 302) -> RedirectResponse:
    return RedirectResponse(location, status_code=code)


def url_for(endpoint: str, **values: Any) -> str:
    app = _get_current_app()
    if endpoint == "static" and "filename" in values:
        values = dict(values)
        values["path"] = values.pop("filename")
    if endpoint == "static":
        return str(app.url_path_for(endpoint, **values))
    route = next((route for route in app.router.routes if getattr(route, "name", None) == endpoint), None)
    param_names: set[str] = set()
    if route is not None:
        path_template = getattr(route, "path", "") or ""
        param_names = {match.group(1) for match in re.finditer(r"{([^}:]+)(?::[^}]+)?}", path_template)}
    path_values = {key: value for key, value in values.items() if key in param_names}
    query_values = {key: value for key, value in values.items() if key not in param_names}
    path = str(app.url_path_for(endpoint, **path_values))
    if not query_values:
        return path
    return f"{path}?{urlencode(query_values, doseq=True)}"


def render_template(template_name: str, **context: Any) -> HTMLResponse:
    app = _get_current_app()
    request_context = _get_request()
    merged: dict[str, Any] = {
        "request": request_context,
        "session": _get_session(),
        "g": _get_g(),
        "url_for": url_for,
        "get_flashed_messages": get_flashed_messages,
    }
    for processor in app._context_processors:
        merged.update(processor() or {})
    merged.update(context)
    rendered = app.jinja_env.get_template(template_name).render(**merged)
    return HTMLResponse(rendered)


def make_response(*args: Any) -> Response:
    if not args:
        return Response()
    if len(args) == 1:
        return _get_current_app()._make_response(args[0])
    return _get_current_app()._make_response(args)


def send_file(
    path_or_file: str | Path | BytesIO,
    mimetype: str | None = None,
    as_attachment: bool = False,
    download_name: str | None = None,
) -> Response:
    if isinstance(path_or_file, (str, Path)):
        file_path = Path(path_or_file)
        media_type = mimetype or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        response = FileResponse(str(file_path), media_type=media_type)
        filename = download_name or file_path.name
    else:
        file_buffer = path_or_file
        try:
            file_buffer.seek(0)
        except Exception:
            pass
        response = Response(file_buffer.read(), media_type=mimetype or "application/octet-stream")
        filename = download_name or "download"
    if filename:
        disposition = "attachment" if as_attachment else "inline"
        response.headers["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    return response


def send_from_directory(
    directory: str | Path,
    path: str,
    mimetype: str | None = None,
    as_attachment: bool = False,
    download_name: str | None = None,
) -> Response:
    base_dir = Path(directory).resolve()
    target = (base_dir / path).resolve()
    try:
        target.relative_to(base_dir)
    except ValueError as exc:
        raise NotFound() from exc
    if not target.exists() or not target.is_file():
        raise NotFound()
    return send_file(
        target,
        mimetype=mimetype,
        as_attachment=as_attachment,
        download_name=download_name or target.name,
    )


Request = RequestCompat


__all__ = [
    "Flask",
    "Request",
    "abort",
    "current_app",
    "flash",
    "g",
    "get_flashed_messages",
    "has_request_context",
    "jsonify",
    "make_response",
    "redirect",
    "render_template",
    "request",
    "send_file",
    "send_from_directory",
    "session",
    "url_for",
]
