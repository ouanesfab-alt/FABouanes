import os
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from app.web.deps import require_permission, template_context, templates
from app.core.db_helpers import db_manager
from app.modules.assistant.service import run_assistant_agent

router = APIRouter()

def get_gemini_api_key() -> str:
    """Récupère la clé d'API depuis l'environnement ou les paramètres de la base de données."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        api_key = db_manager.get_setting("gemini_api_key", "").strip()
    return api_key

@router.get("/assistant", name="assistant_chat_page")
async def assistant_page(request: Request):
    denied = require_permission(request, "assistant.read")
    if denied:
        return denied
        
    api_key = get_gemini_api_key()
    has_key = bool(api_key)
    
    return templates.TemplateResponse("assistant.html", template_context(
        request,
        has_key=has_key,
        title="Assistant IA - FABOuanes"
    ))

@router.post("/assistant/chat")
async def assistant_chat(request: Request):
    denied = require_permission(request, "assistant.write")
    if denied:
        return JSONResponse({"success": False, "error": "Permission refusée."}, status_code=403)
        
    api_key = get_gemini_api_key()
    if not api_key:
        return JSONResponse({
            "success": False,
            "error": "Clé d'API Gemini manquante. Veuillez la configurer dans l'onglet de droite."
        })
        
    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        
        if not message:
            return JSONResponse({"success": False, "error": "Message vide."})
            
        # Construire le message utilisateur au format Gemini API
        new_message = {
            "role": "user",
            "parts": [{"text": message}]
        }
        
        # Lancer l'agent conversationnel
        response_text = await run_assistant_agent(history + [new_message], api_key)
        
        return JSONResponse({
            "success": True,
            "response": response_text
        })
    except Exception as e:
        return JSONResponse({
            "success": False,
            "error": f"Une erreur s'est produite : {str(e)}"
        })

@router.post("/assistant/settings", name="assistant_save_settings")
async def save_settings(request: Request):
    denied = require_permission(request, "assistant.write")
    if denied:
        return denied
        
    form = await request.form()
    api_key = form.get("gemini_api_key", "").strip()
    
    db_manager.set_setting("gemini_api_key", api_key)
    
    # Rediriger vers l'assistant
    return RedirectResponse("/assistant", status_code=303)
