import os
import json
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from app.web.deps import require_permission, template_context, templates
from app.core.db_helpers import db_manager
from app.core.security import encrypt_val
from app.modules.assistant.service import (
    get_gemini_api_key,
    get_encryption_key,
    run_assistant_agent_generator,
    start_ollama
)

router = APIRouter()

@router.get("/assistant", name="assistant_chat_page")
async def assistant_page(request: Request):
    denied = require_permission(request, "assistant.read")
    if denied:
        return denied
        
    api_key = get_gemini_api_key()
    selected_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    if not selected_model:
      selected_model = "gemini-3.1-flash-lite"
        
    is_local = selected_model.lower() in ("local", "ollama")
    has_key = bool(api_key) or is_local
    
    return templates.TemplateResponse("assistant.html", template_context(
        request,
        has_key=has_key,
        selected_model=selected_model,
        title="Sabrina - Assistante IA"
    ))

@router.post("/assistant/chat")
async def assistant_chat(request: Request):
    denied = require_permission(request, "assistant.write")
    if denied:
        return JSONResponse({"success": False, "error": "Permission refusée."}, status_code=403)
        
    selected_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    is_local = selected_model.lower() in ("local", "ollama")
    
    api_key = get_gemini_api_key()
    if not is_local and not api_key:
        return JSONResponse({
            "success": False,
            "error": "Clé d'API Gemini manquante. Veuillez la configurer dans la barre latérale."
        })
        
    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        file_obj = body.get("file")
        confirmed_query = body.get("confirmed_query")
        
        if not message:
            return JSONResponse({"success": False, "error": "Message vide."})
            
        # Construire le message utilisateur au format Gemini API
        new_message = {
            "role": "user",
            "parts": [{"text": message}]
        }
        
        if file_obj and isinstance(file_obj, dict):
            mime_type = file_obj.get("mime_type")
            data = file_obj.get("data")
            if mime_type and data:
                new_message["parts"].append({
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": data
                    }
                })
        
        # Retourner un StreamingResponse pour le flux d'événements (SSE)
        async def chat_event_generator():
            try:
                async for event in run_assistant_agent_generator(
                    history + [new_message], 
                    api_key or "", 
                    confirmed_query
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
            finally:
                from app.core.request_state import get_request_state
                state = get_request_state()
                if state is not None:
                    db = getattr(state, "db", None)
                    if db is not None:
                        try:
                            db.close()
                        except Exception:
                            pass
                    read_db = getattr(state, "read_db", None)
                    if read_db is not None:
                        try:
                            read_db.close()
                        except Exception:
                            pass
                
        return StreamingResponse(chat_event_generator(), media_type="text/event-stream")
        
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
        
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
        api_key = data.get("gemini_api_key", "").strip()
        selected_model = data.get("gemini_model", "").strip()
    else:
        form = await request.form()
        api_key = form.get("gemini_api_key", "").strip()
        selected_model = form.get("gemini_model", "").strip()
        
    if api_key:
        # Si la clé saisie n'est pas masquée, on la chiffre avant de l'enregistrer
        if not api_key.startswith("••••"):
            encrypted_key = encrypt_val(api_key, get_encryption_key())
            db_manager.set_setting("gemini_api_key", encrypted_key)
            
    if selected_model:
        db_manager.set_setting("gemini_model", selected_model)
        if selected_model.lower() in ("local", "ollama"):
            try:
                start_ollama()
            except Exception:
                pass
        
    is_ajax = request.headers.get("x-requested-with") == "XMLHttpRequest" or \
              "application/json" in request.headers.get("accept", "") or \
              "application/json" in content_type
              
    if is_ajax:
        return JSONResponse({"success": True})
        
    return RedirectResponse("/assistant", status_code=303)
