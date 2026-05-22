from __future__ import annotations

import secrets
import re
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from starlette.routing import NoMatchFound

from app.core.auth_cookie import AUTH_COOKIE_NAME, read_auth_cookie_value
from app.core.config import settings
from app.core.permissions import has_permission
from app.core.runtime_paths import paths
from app.repositories.user_repository import get_user_by_id


from app.web.compat import COMPAT_ROUTE_MAP


class TemplateRequestProxy:
    def __init__(self, request: Request):
        self._request = request
        route = request.scope.get("route")
        self.endpoint = getattr(route, "name", "") or request.scope.get("endpoint_name", "")
        self.path = request.url.path
        self.method = request.method
        self.headers = request.headers
        self.args = request.query_params
        self.query_params = request.query_params
        self.scheme = request.url.scheme
        self.host = request.headers.get("host", "")

    def url_for(self, name: str, **params: Any) -> str:
        return app_url_for(self._request, name, **params)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._request, item)


templates = Jinja2Templates(directory=str(paths.templates_dir))


def _money_filter(value: Any) -> str:
    try:
        if value is None:
            return "0,00 DA"
        amount = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
        return f"{amount} DA"
    except Exception:
        return "0,00 DA"


def _qty_filter(value: Any) -> str:
    try:
        if value is None:
            return "0"
        number = float(value)
        if abs(number - round(number)) < 1e-9:
            return str(int(round(number)))
        rendered = f"{number:,.2f}".replace(",", " ").replace(".", ",")
        return rendered.rstrip("0").rstrip(",")
    except Exception:
        return str(value or "0")


def _query_string(params: dict[str, Any]) -> str:
    usable = {key: value for key, value in params.items() if value not in (None, "")}
    if not usable:
        return ""
    return "?" + urlencode(usable, doseq=True)


def _append_query(url: str, params: dict[str, Any]) -> str:
    query = _query_string(params)
    if not query:
        return url
    separator = "&" if "?" in url else "?"
    return url + separator + query.lstrip("?")


def _route_param_names(app, name: str) -> set[str] | None:
    for route in app.routes:
        if getattr(route, "name", None) == name:
            return set(getattr(route, "param_convertors", {}).keys())
    return None


def app_url_for(request: Request, name: str, **params: Any) -> str:
    if name == "static":
        filename = str(params.get("filename", "")).lstrip("/")
        query_params = {key: value for key, value in params.items() if key != "filename"}
        return _append_query(f"/static/{filename}", query_params)
    route_params = _route_param_names(request.app, name)
    try:
        if route_params is None:
            url_path = request.app.url_path_for(name, **params)
            return str(request.base_url.replace(path=str(url_path), query=""))
        path_params = {key: value for key, value in params.items() if key in route_params}
        query_params = {key: value for key, value in params.items() if key not in route_params}
        url_path = request.app.url_path_for(name, **path_params)
        base_url = str(request.base_url.replace(path=str(url_path), query=""))
        return _append_query(base_url, query_params)
    except NoMatchFound:
        if name not in COMPAT_ROUTE_MAP:
            raise
        template = COMPAT_ROUTE_MAP[name]
        if "{query}" in template:
            return _append_query(template.format(query=""), params)
        placeholders = set(re.findall(r"{([a-zA-Z_][a-zA-Z0-9_]*)}", template))
        path_params = {key: value for key, value in params.items() if key in placeholders}
        query_params = {key: value for key, value in params.items() if key not in placeholders}
        return _append_query(template.format(**path_params), query_params)


def flash(request: Request, message: str, category: str = "success") -> None:
    flashes = list(request.session.get("_flashes", []))
    flashes.append([category, message])
    request.session["_flashes"] = flashes


def pop_flashed_messages(request: Request, with_categories: bool = False):
    messages = list(request.session.pop("_flashes", []))
    if with_categories:
        return messages
    return [message for _, message in messages]


def ensure_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        request.session["csrf_token"] = token
    return token


async def csrf_protect(request: Request) -> None:
    if request.method != "POST":
        return
    if request.url.path.startswith("/api/v1/"):
        return
    expected = request.session.get("csrf_token")
    if not expected:
        raise ValueError("CSRF token invalide.")
    content_type = request.headers.get("content-type", "")
    supplied = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token") or request.headers.get("X-Csrf-Token")
    if "application/json" in content_type:
        payload = await request.json()
        supplied = supplied or payload.get("csrf_token")
    else:
        form = await request.form()
        supplied = supplied or form.get("csrf_token")
    if supplied != expected:
        raise ValueError("CSRF token invalide.")


def get_current_user(request: Request):
    return getattr(request.state, "user", None)


def current_user_ns(request: Request) -> SimpleNamespace | None:
    user = get_current_user(request)
    if not user:
        return None
    return SimpleNamespace(**user)


def load_user_from_session(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        user_id = read_auth_cookie_value(request.cookies.get(AUTH_COOKIE_NAME))
    if not user_id:
        return None
    user = get_user_by_id(int(user_id))
    if not user or not int(user.get("is_active", 1) or 0):
        request.session.clear()
        return None
    return user


def login_redirect() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def require_user(request: Request):
    user = get_current_user(request)
    if not user:
        return login_redirect()
    return None


def require_permission(request: Request, permission: str):
    user = get_current_user(request)
    if not user:
        return login_redirect()
    if not has_permission(user, permission):
        flash(request, "Acces refuse pour cette action.", "danger")
        return RedirectResponse("/", status_code=303)
    return None


def template_context(request: Request, **context: Any) -> dict[str, Any]:
    csrf_token = ensure_csrf_token(request)
    proxy = TemplateRequestProxy(request)
    user = current_user_ns(request)
    from app.core.request_state import get_state_value
    csp_nonce = get_state_value("csp_nonce") or ""
    return {
        "request": proxy,
        "raw_request": request,
        "csrf_token": csrf_token,
        "is_desktop_app": settings.desktop_mode,
        "g": SimpleNamespace(user=user),
        "csp_nonce": csp_nonce,
        **context,
    }


def _dt_filter(value: Any, length: int = 16) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        if length <= 10:
            return value.strftime("%Y-%m-%d")
        return value.strftime("%Y-%m-%d %H:%M")
    elif hasattr(value, "isoformat"):
        return value.isoformat()[:length]
    return str(value)[:length]


def _custom_tojson_filter(value: Any, *args: Any, **kwargs: Any) -> Any:
    import json
    import decimal
    try:
        from markupsafe import Markup
    except ImportError:
        from jinja2 import Markup

    class SafeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, decimal.Decimal):
                return float(obj)
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            try:
                return super().default(obj)
            except TypeError:
                return str(obj)

    rendered = json.dumps(value, cls=SafeEncoder, ensure_ascii=False)
    safe_rendered = (
        rendered.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("'", "\\u0027")
    )
    return Markup(safe_rendered)


@pass_context
def _url_for(context, name: str, **params: Any) -> str:
    request = context["request"]
    return request.url_for(name, **params)


@pass_context
def _get_flashed_messages(context, with_categories: bool = False):
    request = context["request"]
    return pop_flashed_messages(request._request, with_categories=with_categories)


templates.env.globals["url_for"] = _url_for
templates.env.globals["get_flashed_messages"] = _get_flashed_messages
templates.env.filters["money"] = _money_filter
templates.env.filters["qty"] = _qty_filter
templates.env.filters["dt"] = _dt_filter
templates.env.filters["tojson"] = _custom_tojson_filter
