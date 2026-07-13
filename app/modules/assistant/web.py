import os
import json
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse, StreamingResponse
from app.web.deps import require_permission
from app.core.db_helpers import db_manager
from app.core.security import encrypt_val
from app.modules.assistant.schema_context import get_gemini_api_key, get_encryption_key
from app.modules.assistant.service import (
    run_assistant_agent_generator,
    start_ollama
)

router = APIRouter()

@router.get("/assistant", name="assistant_chat_page")
async def assistant_page(request: Request):
    """Redirect to dashboard — Sabrina is now integrated directly there."""
    return RedirectResponse("/dashboard", status_code=303)

@router.get("/assistant/briefing")
async def assistant_briefing(request: Request):
    """Endpoint pour le Morning Briefing proactif de Sabrina."""
    denied = require_permission(request, "assistant.read")
    if denied:
        return JSONResponse({"has_briefing": False}, status_code=403)
    try:
        from app.modules.assistant.briefing import generate_briefing
        result = generate_briefing()
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({"has_briefing": False, "error": str(e)})

@router.post("/assistant/chat")
async def assistant_chat(request: Request):
    denied = require_permission(request, "assistant.write")
    if denied:
        return JSONResponse({"success": False, "error": "Permission refusée."}, status_code=403)

    selected_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    is_local = selected_model.lower() in ("local", "ollama")

    try:
        body = await request.json()
        message = body.get("message", "").strip()
        history = body.get("history", [])
        file_obj = body.get("file")
        confirmed_query = body.get("confirmed_query")
        req_api_key = body.get("gemini_api_key", "").strip()

        # Determine active API Key (from request or fallback to DB)
        api_key = ""
        if req_api_key and not req_api_key.startswith("••••"):
            api_key = req_api_key
            try:
                stored_key_encrypted = db_manager.get_setting("gemini_api_key", "").strip()
                from app.core.security import decrypt_val
                stored_key_decrypted = decrypt_val(stored_key_encrypted, get_encryption_key()) or ""
                if api_key != stored_key_decrypted:
                    encrypted_key = encrypt_val(api_key, get_encryption_key())
                    db_manager.set_setting("gemini_api_key", encrypted_key)
            except Exception:
                pass
        
        if not api_key:
            api_key = get_gemini_api_key()

        if not is_local and not api_key:
            return JSONResponse({
                "success": False,
                "error": "Clé d'API Gemini manquante. Veuillez la configurer dans la barre latérale."
            })

        if not message:
            return JSONResponse({"success": False, "error": "Message vide."})

        # Check if the message is a recorded audio note
        # Format: [AUDIO:data:audio/webm;base64,...|transcript]
        import re
        audio_match = re.match(r"^\[AUDIO:([^|]+)\|(.*)\]$", message)
        audio_inline = None
        if audio_match:
            data_url   = audio_match.group(1).strip()  # e.g. data:audio/webm;base64,AAA…
            transcript = audio_match.group(2).strip()
            # Extract mime type and raw base64 from the data URL
            if data_url.startswith("data:") and ";base64," in data_url:
                meta, b64_data = data_url.split(";base64,", 1)
                mime_type_audio = meta.split("data:")[1]  # e.g. audio/webm
                audio_inline = {"mimeType": mime_type_audio, "data": b64_data}
            if transcript:
                message_text_for_llm = transcript
            else:
                message_text_for_llm = "Transcris ce message audio et réponds en conséquence."
        else:
            message_text_for_llm = message

        # Construire le message utilisateur au format Gemini API
        new_message = {
            "role": "user",
            "parts": [{"text": message_text_for_llm}]
        }
        # Attach audio inline data so Gemini can transcribe and understand the voice note
        if audio_inline:
            new_message["parts"].append({"inlineData": audio_inline})

        if file_obj and isinstance(file_obj, dict):
            mime_type = file_obj.get("mime_type")
            data = file_obj.get("data")
            filename = file_obj.get("name", "upload.xlsx")

            is_excel = (
                filename.lower().endswith((".xlsx", ".xlsm")) or
                (mime_type and ("sheet" in mime_type.lower() or "excel" in mime_type.lower()))
            )

            if is_excel and mime_type and data:
                import base64
                from pathlib import Path
                from app.core.config import BASE_DIR

                import_dir = Path(BASE_DIR) / "app" / "runtime" / "imports"
                import_dir.mkdir(parents=True, exist_ok=True)

                safe_name = "".join(c for c in filename if c.isalnum() or c in (".", "_", "-")).strip()
                if not safe_name:
                    safe_name = "temp_upload.xlsx"

                target_path = import_dir / safe_name
                try:
                    file_bytes = base64.b64decode(data)
                    with open(target_path, "wb") as f:
                        f.write(file_bytes)

                    abs_path_str = os.path.abspath(str(target_path))
                    new_message["parts"][0]["text"] += f"\n\n[INFO SYSTÈME : Fichier Excel joint '{filename}' enregistré temporairement sur le serveur à l'emplacement : {abs_path_str}. Pour l'importer, appelle l'outil approprié comme `import_client_excel` ou `import_client_history_excel` avec cet emplacement exact.]"
                except Exception as e:
                    new_message["parts"][0]["text"] += f"\n\n[INFO SYSTÈME : Échec de l'enregistrement du fichier Excel joint '{filename}' : {str(e)}]"
            elif mime_type and data:
                new_message["parts"].append({
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": data
                    }
                })

        # Retourner un StreamingResponse pour le flux d'événements (SSE)
        from app.web.deps import get_current_user
        user = get_current_user(request)
        user_role = getattr(user, "role", "operator")

        async def chat_event_generator():
            try:
                messages_to_send = history if confirmed_query else history + [new_message]
                async for event in run_assistant_agent_generator(
                    messages_to_send,
                    api_key or "",
                    confirmed_query,
                    user_role=user_role
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

    return RedirectResponse("/dashboard", status_code=303)


@router.post("/assistant/test-key")
async def test_api_key_endpoint(request: Request):
    denied = require_permission(request, "assistant.write")
    if denied:
        return JSONResponse({"success": False, "error": "Permission refusée."}, status_code=403)
    try:
        from app.modules.assistant.schema_context import get_gemini_api_key
        key = get_gemini_api_key()
        if not key:
            return JSONResponse({"success": False, "error": "Aucune clé d'API enregistrée."})
        
        import httpx
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "Say ok"}]}]}
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            if res.status_code == 200:
                return JSONResponse({"success": True, "message": "Connexion établie avec succès avec Google Gemini !"})
            else:
                try:
                    err_data = res.json()
                    err_msg = err_data.get("error", {}).get("message", res.text)
                    err_reason = ""
                    details = err_data.get("error", {}).get("details", [])
                    if details and isinstance(details, list):
                        err_reason = details[0].get("reason", "")
                except Exception:
                    err_msg = res.text
                    err_reason = ""
                
                if "API_KEY_SERVICE_BLOCKED" in err_reason or "api_key_service_blocked" in err_msg.lower():
                    friendly_err = "Clé bloquée : L'API Generative Language (Gemini) est restreinte ou désactivée pour cette clé dans la console Google Cloud. Veuillez créer une clé directement depuis Google AI Studio."
                elif "leaked" in err_msg.lower():
                    friendly_err = "Clé révoquée : Google a signalé et désactivé cette clé pour des raisons de sécurité (exposée/leakée)."
                else:
                    friendly_err = f"Erreur de l'API Google ({res.status_code}) : {err_msg}"
                return JSONResponse({"success": False, "error": friendly_err})
    except Exception as e:
        return JSONResponse({"success": False, "error": f"Erreur de communication : {str(e)}"})
