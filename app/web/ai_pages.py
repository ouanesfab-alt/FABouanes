"""Page IA — Chat Gemini intégré à FABOuanes."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.web.deps import get_current_user, template_context, templates

router = APIRouter()


@router.get("/ai", name="ai_chat")
async def ai_chat_page(request: Request):
    if not get_current_user(request):
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(
        "ai_chat.html",
        template_context(request),
    )
