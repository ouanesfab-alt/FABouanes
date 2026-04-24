from __future__ import annotations

from functools import wraps

from fabouanes.fastapi_compat import g, redirect, url_for

from fabouanes.core.permissions import (
    PERMISSION_SETTINGS_MANAGE,
    has_permission,
    permission_denied_response,
)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if getattr(g, "user", None) is None:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = getattr(g, "user", None)
        if user is None:
            return redirect(url_for("login"))
        if not has_permission(user, PERMISSION_SETTINGS_MANAGE):
            return permission_denied_response(PERMISSION_SETTINGS_MANAGE)
        return view(*args, **kwargs)

    return wrapped
