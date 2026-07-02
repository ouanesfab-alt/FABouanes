from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.core.auth_cookie import AUTH_COOKIE_NAME, build_auth_cookie_value
from app.core.config import settings
from app.web.deps import csrf_protect, flash, get_current_user, login_redirect, template_context, templates
from app.core.activity import log_activity
from app.core.audit import audit_event
from app.services.auth_service import attempt_login, change_user_password
from app.core.rate_limit import limiter



router = APIRouter()


@router.get("/login", name="login")
async def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", template_context(request))


@router.post("/login", name="login")
@limiter.limit("5/minute")
async def login_submit(request: Request):
    if get_current_user(request):
        return RedirectResponse("/", status_code=303)
    await csrf_protect(request)
    form = await request.form()
    result = await attempt_login(form.get("username", ""), form.get("password", ""), request)
    if result["ok"]:
        user = result["user"]
        # request.session.clear() est déjà géré par la rotation dans attempt_login, on garde les attributs restants
        request.session["user_id"] = user["id"]
        request.session["remember"] = bool(form.get("remember"))
        flash(request, "Connexion réussie.", "success")
        target = "/change-password" if int(user.get("must_change_password", 0) or 0) else "/"
        if int(user.get("must_change_password", 0) or 0):
            flash(request, "Changez immédiatement le mot de passe administrateur par défaut.", "warning")
        response = RedirectResponse(target, status_code=303)
        from app.core.security import get_client_fingerprint
        response.set_cookie(
            AUTH_COOKIE_NAME,
            build_auth_cookie_value(int(user["id"]), get_client_fingerprint(request)),
            max_age=settings.session_max_age if request.session.get("remember") else None,
            httponly=True,
            samesite="lax",
            secure=settings.session_cookie_secure,
            path="/",
        )
        return response
    flash(request, result["message"], "danger")
    status_code = 429 if result.get("status") == 429 else 200
    return templates.TemplateResponse("login.html", template_context(request), status_code=status_code)


@router.get("/change-password", name="change_password")
async def change_password_page(request: Request):
    redirect = login_redirect() if not get_current_user(request) else None
    if redirect:
        return redirect
    return templates.TemplateResponse("change_password.html", template_context(request))


@router.post("/change-password", name="change_password")
async def change_password_submit(request: Request):
    user = get_current_user(request)
    if not user:
        return login_redirect()
    await csrf_protect(request)
    form = await request.form()
    result = await change_user_password(
        user["id"],
        form.get("current_password", ""),
        form.get("new_password", ""),
        form.get("confirm_password", ""),
    )
    flash(request, result["message"], "success" if result["ok"] else "danger")
    return RedirectResponse("/" if result["ok"] else "/change-password", status_code=303)


@router.get("/logout", name="logout")
async def logout(request: Request):
    user = get_current_user(request)
    if user:
        log_activity("logout", "user", user["id"], f"Déconnexion de {user['username']}")
        audit_event("logout", "user", user["id"], after={"username": user["username"]})
    request.session.clear()
    flash(request, "Vous êtes déconnecté.", "success")
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return response
