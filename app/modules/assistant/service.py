import os
import json
import logging
import httpx
from typing import Any, Dict, List
from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant")

TABLE_SCHEMAS = {
    "clients": "id (BIGINT), name (TEXT), phone (TEXT), address (TEXT), notes (TEXT), opening_credit (NUMERIC), created_at (TIMESTAMPTZ) - Liste des clients",
    "suppliers": "id (BIGINT), name (TEXT), phone (TEXT), address (TEXT), notes (TEXT), created_at (TIMESTAMPTZ) - Liste des fournisseurs",
    "raw_materials": "id (BIGINT), name (TEXT), unit (TEXT), stock_qty (NUMERIC), avg_cost (NUMERIC), alert_threshold (NUMERIC), threshold_qty (NUMERIC) - Matières premières en stock",
    "finished_products": "id (BIGINT), name (TEXT), default_unit (TEXT), stock_qty (NUMERIC), sale_price (NUMERIC), avg_cost (NUMERIC), alert_threshold (NUMERIC) - Produits finis en stock",
    "purchases": "id (BIGINT), supplier_id (BIGINT), raw_material_id (BIGINT), finished_product_id (BIGINT), quantity (NUMERIC), unit (TEXT), unit_price (NUMERIC), total (NUMERIC), purchase_date (DATE), notes (TEXT), created_at (TIMESTAMPTZ) - Achats de matières premières ou de produits finis",
    "sales": "id (BIGINT), client_id (BIGINT), finished_product_id (BIGINT), quantity (NUMERIC), unit (TEXT), unit_price (NUMERIC), total (NUMERIC), sale_type (TEXT 'cash' ou 'credit'), amount_paid (NUMERIC), balance_due (NUMERIC), cost_price_snapshot (NUMERIC), profit_amount (NUMERIC), sale_date (DATE), notes (TEXT), created_at (TIMESTAMPTZ) - Ventes de produits finis",
    "raw_sales": "id (BIGINT), client_id (BIGINT), raw_material_id (BIGINT), quantity (NUMERIC), unit (TEXT), unit_price (NUMERIC), total (NUMERIC), sale_type (TEXT 'cash' ou 'credit'), amount_paid (NUMERIC), balance_due (NUMERIC), cost_price_snapshot (NUMERIC), profit_amount (NUMERIC), sale_date (DATE), notes (TEXT), created_at (TIMESTAMPTZ) - Ventes de matières premières",
    "payments": "id (BIGINT), client_id (BIGINT), amount (NUMERIC), payment_date (DATE), notes (TEXT), created_at (TIMESTAMPTZ) - Règlements ou versements reçus des clients pour leurs crédits",
    "expenses": "id (BIGINT), date (DATE), category (TEXT), description (TEXT), amount (NUMERIC), payment_method (TEXT) - Dépenses et charges diverses",
    "production_batches": "id (BIGINT), product_id (BIGINT), quantity_produced (NUMERIC), production_date (DATE), notes (TEXT) - Lots de fabrication de produits finis",
    "production_batch_items": "id (BIGINT), batch_id (BIGINT), raw_material_id (BIGINT), quantity_used (NUMERIC) - Matières premières consommées lors de la production"
}

def get_schema() -> Dict[str, Any]:
    """Retourne la description de la structure de la base de données."""
    return {"schema": TABLE_SCHEMAS}

def execute_readonly_sql(query: str) -> Dict[str, Any]:
    """Exécute une requête SQL SELECT en lecture seule et retourne le résultat."""
    clean_query = query.strip().lower()
    
    # Validation basique
    if not clean_query.startswith(("select", "with", "show", "explain")):
        return {"error": "Seules les requêtes SELECT, WITH, EXPLAIN ou SHOW sont autorisées pour des raisons de sécurité."}
    
    # Interdiction des opérations d'écriture cachées ou chaînées
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "grant", "revoke", "replace"]
    for word in forbidden:
        if f" {word} " in f" {clean_query} " or clean_query.startswith(f"{word} "):
            return {"error": f"Opération '{word}' interdite pour des raisons de sécurité."}
            
    try:
        # Exécution dans une transaction et rollback automatique systématique
        with db_manager.db_transaction() as conn:
            try:
                cur = conn.execute(query)
                rows = cur.fetchall()
                cur.close()
                return {"rows": [dict(r) for r in rows]}
            finally:
                conn.rollback() # Toujours rollback pour annuler toute modification accidentelle
    except Exception as e:
        return {"error": f"Erreur SQL : {str(e)}"}

async def call_gemini_api(contents: List[Dict[str, Any]], api_key: str) -> Dict[str, Any]:
    """Appelle l'API Gemini 2.5 Flash avec les messages et outils définis."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    tools = [
        {
            "functionDeclarations": [
                {
                    "name": "get_schema",
                    "description": "Retourne le schéma complet de la base de données (tables et colonnes)."
                },
                {
                    "name": "execute_readonly_sql",
                    "description": "Exécute une requête SQL SELECT en lecture seule et retourne le résultat sous forme de lignes JSON.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "La requête SQL SELECT complète à exécuter."
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]
    
    system_instruction = (
        "Tu es l'Assistant IA de FABOuanes, un progiciel de gestion commerciale et de stock.\n"
        "Tu as un accès direct à la base de données via des outils de lecture.\n"
        "Rédige tes réponses en français, de manière claire, concise et professionnelle.\n"
        "Utilise le formatage Markdown (tableaux, listes, gras) pour rendre les données très lisibles.\n"
        "Pour répondre aux questions sur les données, utilise `get_schema` puis génère une requête SQL que tu exécuteras via `execute_readonly_sql`.\n"
        "Règles STRICTES :\n"
        "1. Ne modifie JAMAIS de données.\n"
        "2. Ne lis jamais la table 'users' (contient les mots de passe hachés).\n"
        "3. Sois honnête si la base ne contient pas l'info."
    )
    
    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=60.0)
        response.raise_for_status()
        return response.json()

async def run_assistant_agent(messages: List[Dict[str, Any]], api_key: str) -> str:
    """Orchestre la boucle d'agent avec Gemini (Tool Calling)."""
    # Copie locale de l'historique pour l'échange en cours
    contents = list(messages)
    
    # Limite de sécurité sur le nombre de tours d'appels d'outils successifs
    max_turns = 6
    for turn in range(max_turns):
        try:
            res = await call_gemini_api(contents, api_key)
        except Exception as exc:
            logger.error("Erreur d'appel API Gemini: %s", exc)
            return "Désolé, impossible de joindre l'API Gemini. Vérifiez votre clé d'API dans les paramètres."

        candidates = res.get("candidates", [])
        if not candidates:
            return "L'assistant n'a pas renvoyé de réponse."

        content_obj = candidates[0].get("content", {})
        parts = content_obj.get("parts", [])
        
        # Ajouter la réponse du modèle à l'historique pour le tour suivant
        contents.append(content_obj)
        
        # Vérifier si le modèle a demandé un appel d'outil
        tool_calls = [p for p in parts if "functionCall" in p]
        
        if not tool_calls:
            # Réponse textuelle finale trouvée
            text_parts = [p.get("text", "") for p in parts if "text" in p]
            return "".join(text_parts)

        # Si le modèle a demandé des appels d'outils, on les exécute tous
        function_responses = []
        for part in tool_calls:
            func_call = part["functionCall"]
            func_name = func_call["name"]
            func_args = func_call.get("args", {})
            
            logger.info("Agent Call: Execute function '%s' with args %s", func_name, func_args)
            
            if func_name == "get_schema":
                output = get_schema()
            elif func_name == "execute_readonly_sql":
                sql_query = func_args.get("query", "")
                output = execute_readonly_sql(sql_query)
            else:
                output = {"error": f"Outil '{func_name}' inconnu."}
                
            function_responses.append({
                "functionResponse": {
                    "name": func_name,
                    "response": {"output": output}
                }
            })
            
        # Ajouter les réponses de fonction dans les contenus de la conversation
        contents.append({
            "role": "function",
            "parts": function_responses
        })
        
    return "La requête a dépassé la limite de tours d'agent sans retourner de réponse textuelle."
