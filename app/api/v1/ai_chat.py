"""Endpoint proxy vers l'API Gemini — Chat IA FABOuanes."""
from __future__ import annotations

import os
import httpx

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_api_user

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "/gemini-2.0-flash:generateContent"
)

SYSTEM_PROMPT = (
    "Tu es un assistant général. "
    "Réponds toujours en français de façon claire et concise."
)


@router.post("/chat")
async def ai_chat(request: Request):
    require_api_user(request)

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return JSONResponse(
            {"error": "Clé API Gemini non configurée. Ajoutez GEMINI_API_KEY dans votre fichier .env"},
            status_code=503,
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Corps JSON invalide."}, status_code=400)

    history = body.get("history", [])
    user_message = body.get("message", "").strip()

    if not user_message:
        return JSONResponse({"error": "Message vide."}, status_code=400)

    # Construit l'historique au format Gemini
    contents = [
        {"role": "user",  "parts": [{"text": SYSTEM_PROMPT}]},
        {"role": "model", "parts": [{"text": "Compris."}]},
    ]
    for msg in history[-20:]:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{GEMINI_API_URL}?key={api_key}", json=payload)
        if resp.status_code != 200:
            return JSONResponse(
                {"error": f"Erreur API Gemini ({resp.status_code}): {resp.text[:300]}"},
                status_code=502,
            )
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return JSONResponse({"reply": text})
    except httpx.TimeoutException:
        return JSONResponse({"error": "Délai d'attente dépassé. Réessayez."}, status_code=504)
    except Exception as exc:
        return JSONResponse({"error": f"Erreur serveur : {str(exc)}"}, status_code=500)
