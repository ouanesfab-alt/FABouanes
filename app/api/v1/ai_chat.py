"""Endpoint proxy vers les API IA — Gemini / OpenAI / Mistral."""
from __future__ import annotations

import os
import httpx

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_api_user

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

# ── Providers ───────────────────────────────────────────────
PROVIDERS = {
    "gemini-2.0-flash": {
        "label": "Gemini 2.0 Flash",
        "env_key": "GEMINI_API_KEY",
        "type": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
    },
    "gemini-2.5-flash": {
        "label": "Gemini 2.5 Flash",
        "env_key": "GEMINI_API_KEY",
        "type": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent",
    },
    "gemini-2.5-pro": {
        "label": "Gemini 2.5 Pro",
        "env_key": "GEMINI_API_KEY",
        "type": "gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro-preview-05-06:generateContent",
    },
    "gpt-4o-mini": {
        "label": "GPT-4o Mini",
        "env_key": "OPENAI_API_KEY",
        "type": "openai",
        "model": "gpt-4o-mini",
    },
    "gpt-4o": {
        "label": "GPT-4o",
        "env_key": "OPENAI_API_KEY",
        "type": "openai",
        "model": "gpt-4o",
    },
}

SYSTEM_PROMPT = "Tu es un assistant général. Réponds toujours en français de façon claire et concise."


async def _call_gemini(provider: dict, api_key: str, contents: list) -> str:
    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{provider['url']}?key={api_key}", json=payload)
    if resp.status_code != 200:
        raise ValueError(f"Erreur Gemini ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


async def _call_openai(provider: dict, api_key: str, messages: list) -> str:
    payload = {
        "model": provider["model"],
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
    if resp.status_code != 200:
        raise ValueError(f"Erreur OpenAI ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"]


@router.get("/providers")
async def list_providers(request: Request):
    """Retourne la liste des modèles disponibles (ceux dont la clé est configurée)."""
    require_api_user(request)
    available = []
    for key, p in PROVIDERS.items():
        api_key = os.getenv(p["env_key"], "").strip()
        available.append({
            "id": key,
            "label": p["label"],
            "type": p["type"],
            "available": bool(api_key),
        })
    return JSONResponse({"providers": available})


@router.post("/chat")
async def ai_chat(request: Request):
    require_api_user(request)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Corps JSON invalide."}, status_code=400)

    model_id = body.get("model", "gemini-2.0-flash")
    history = body.get("history", [])
    user_message = body.get("message", "").strip()

    if not user_message:
        return JSONResponse({"error": "Message vide."}, status_code=400)

    provider = PROVIDERS.get(model_id)
    if not provider:
        return JSONResponse({"error": f"Modèle inconnu : {model_id}"}, status_code=400)

    api_key = os.getenv(provider["env_key"], "").strip()
    if not api_key:
        return JSONResponse(
            {"error": f"Clé API non configurée ({provider['env_key']}). Ajoutez-la dans .env"},
            status_code=503,
        )

    try:
        if provider["type"] == "gemini":
            contents = [
                {"role": "user", "parts": [{"text": SYSTEM_PROMPT}]},
                {"role": "model", "parts": [{"text": "Compris."}]},
            ]
            for msg in history[-30:]:
                role = "user" if msg.get("role") == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg.get("text", "")}]})
            contents.append({"role": "user", "parts": [{"text": user_message}]})
            reply = await _call_gemini(provider, api_key, contents)

        elif provider["type"] == "openai":
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            for msg in history[-30:]:
                role = "user" if msg.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": msg.get("text", "")})
            messages.append({"role": "user", "content": user_message})
            reply = await _call_openai(provider, api_key, messages)

        else:
            return JSONResponse({"error": "Type de provider non supporté."}, status_code=400)

        return JSONResponse({"reply": reply})

    except httpx.TimeoutException:
        return JSONResponse({"error": "Délai d'attente dépassé. Réessayez."}, status_code=504)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    except Exception as exc:
        return JSONResponse({"error": f"Erreur serveur : {str(exc)}"}, status_code=500)


@router.get("/keys")
async def get_keys_status(request: Request):
    """Retourne quelles clés API sont configurées (sans révéler les valeurs)."""
    require_api_user(request)
    return JSONResponse({
        "gemini": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "openai": bool(os.getenv("OPENAI_API_KEY", "").strip()),
    })


@router.post("/keys")
async def save_keys(request: Request):
    """Enregistre les clés API dans le fichier .env du projet."""
    require_api_user(request)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Corps JSON invalide."}, status_code=400)

    gemini_key = (body.get("gemini_api_key") or "").strip()
    openai_key = (body.get("openai_api_key") or "").strip()

    if not gemini_key and not openai_key:
        return JSONResponse({"error": "Aucune clé fournie."}, status_code=400)

    # Lire le .env existant ou créer un nouveau
    from app.core.config import BASE_DIR
    env_path = BASE_DIR / ".env"

    existing_lines = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    # Mettre à jour ou ajouter les clés
    new_lines = []
    gemini_set = False
    openai_set = False

    for line in existing_lines:
        stripped = line.strip()
        if gemini_key and stripped.startswith("GEMINI_API_KEY="):
            new_lines.append(f"GEMINI_API_KEY={gemini_key}")
            gemini_set = True
        elif openai_key and stripped.startswith("OPENAI_API_KEY="):
            new_lines.append(f"OPENAI_API_KEY={openai_key}")
            openai_set = True
        else:
            new_lines.append(line)

    if gemini_key and not gemini_set:
        new_lines.append(f"GEMINI_API_KEY={gemini_key}")
    if openai_key and not openai_set:
        new_lines.append(f"OPENAI_API_KEY={openai_key}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Appliquer immédiatement dans le process en cours
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
    if openai_key:
        os.environ["OPENAI_API_KEY"] = openai_key

    return JSONResponse({"ok": True})
