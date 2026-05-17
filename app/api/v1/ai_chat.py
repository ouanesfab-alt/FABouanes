"""Endpoint proxy vers l'API Gemini — Chat IA intégré à FABOuanes."""
from __future__ import annotations

import os
import json
import httpx

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.deps import require_api_user
from app.services.transactions_service import transactions_context
from app.modules.reports.repository import ReportsRepository

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"


def _build_business_context() -> str:
    """Construit un résumé des données métier pour enrichir le contexte Gemini."""
    try:
        repo = ReportsRepository()
        summary = repo.get_summary()
        top_clients = repo.get_top_clients_by_revenue(5)
        top_products = repo.get_top_products_by_revenue(5)

        lines = [
            "### Contexte de l'entreprise (FABOuanes — Farine & Dérivés)",
            f"- Chiffre d'affaires total : {summary.get('total_sales', 0):,.0f} DA",
            f"- Bénéfice total : {summary.get('total_profit', 0):,.0f} DA",
            f"- Nombre de ventes : {summary.get('nb_sales', 0)}",
            f"- Total achats : {summary.get('total_purchases', 0):,.0f} DA",
            f"- Total paiements reçus : {summary.get('total_payments', 0):,.0f} DA",
        ]
        if top_clients:
            lines.append("- Top 5 clients : " + ", ".join(c["name"] for c in top_clients))
        if top_products:
            lines.append("- Top 5 produits : " + ", ".join(p["name"] for p in top_products))
        return "\n".join(lines)
    except Exception:
        return "Contexte métier non disponible."


def _system_prompt() -> str:
    biz = _build_business_context()
    return f"""Tu es un assistant commercial expert pour FABOuanes, une entreprise spécialisée dans la vente de farine et produits dérivés en Algérie.
Tu as accès aux données réelles de l'entreprise ci-dessous.
Réponds toujours en français. Sois concis, précis et orienté action.
Utilise des chiffres concrets quand tu analyses. Formate les montants en DA.

{biz}

Aide l'utilisateur avec : analyse des ventes, gestion des dettes, stratégie commerciale, comptabilité, optimisation des stocks, et toute question liée à la gestion de l'entreprise.
"""


@router.post("/chat")
async def ai_chat(request: Request):
    user = require_api_user(request)

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
    contents = []

    # Injecte le system prompt comme premier message utilisateur
    system_text = _system_prompt()
    contents.append({"role": "user", "parts": [{"text": system_text}]})
    contents.append({"role": "model", "parts": [{"text": "Compris ! Je suis prêt à vous aider avec la gestion de FABOuanes."}]})

    for msg in history[-20:]:  # Limite à 20 messages d'historique
        role = "user" if msg.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.get("text", "")}]})

    contents.append({"role": "user", "parts": [{"text": user_message}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{GEMINI_API_URL}?key={api_key}",
                json=payload,
            )
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
