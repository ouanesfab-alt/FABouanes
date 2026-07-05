import os
import json
import logging
import asyncio
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

from decimal import Decimal
from datetime import date, datetime

def serialize_for_json(obj: Any) -> Any:
    """Convertit récursivement les Decimal, date et datetime en types JSON sérialisables."""
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(x) for x in obj]
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj

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
                return {"rows": serialize_for_json([dict(r) for r in rows])}
            finally:
                conn.rollback() # Toujours rollback pour annuler toute modification accidentelle
    except Exception as e:
        return {"error": f"Erreur SQL : {str(e)}"}

def execute_write_sql(query: str) -> Dict[str, Any]:
    """Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour modifier, ajouter ou supprimer des données."""
    clean_query = query.strip().lower()
    
    # Interdiction des opérations destructrices de structure
    forbidden = ["drop", "alter", "truncate", "grant", "revoke"]
    for word in forbidden:
        if f" {word} " in f" {clean_query} " or clean_query.startswith(f"{word} "):
            return {"error": f"Opération de structure '{word}' interdite pour des raisons de sécurité."}
            
    # Ne pas autoriser la lecture/écriture sur la table des utilisateurs
    if "users" in clean_query:
        return {"error": "Accès à la table 'users' interdit."}
        
    try:
        with db_manager.db_transaction() as conn:
            cur = conn.execute(query)
            rowcount = cur.rowcount
            try:
                rows = cur.fetchall()
                result = {"rowcount": rowcount, "rows": serialize_for_json([dict(r) for r in rows])}
            except Exception:
                result = {"rowcount": rowcount}
            cur.close()
            return result
    except Exception as e:
        return {"error": f"Erreur SQL lors de l'écriture : {str(e)}"}

async def call_gemini_api(contents: List[Dict[str, Any]], api_key: str) -> Dict[str, Any]:
    """Appelle l'API Gemini Flash avec les messages et outils définis."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
    
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
                },
                {
                    "name": "execute_write_sql",
                    "description": "Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour ajouter, modifier ou supprimer des données (clients, produits, dépenses, stocks, prix, ventes, etc.). Retourne le nombre de lignes affectées.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "La requête SQL d'écriture complète à exécuter."
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
        "Tu as un accès direct à la base de données via des outils de lecture et d'écriture.\n"
        "Tu comprends parfaitement le français, l'anglais, l'arabe (y compris le dialecte algérien/darja) et le kabyle (Taqbaylit écrit en caractères latins ou arabes).\n"
        "Rédige tes réponses de manière claire, concise et professionnelle, dans la langue choisie par l'utilisateur (ou en français par défaut).\n"
        "Utilise le formatage Markdown (tableaux, listes, gras) pour rendre les données très lisibles.\n"
        "Pour répondre aux questions sur FABOuanes ou les données de l'entreprise, utilise `get_schema` pour comprendre la structure de la base, puis fais tes requêtes SQL.\n"
        "Pour LIRE des données, utilise `execute_readonly_sql`.\n"
        "Pour AJOUTER, MODIFIER ou SUPPRIMER des données (clients, produits, dépenses, stocks, prix, ventes, etc.) à la demande explicite de l'utilisateur, utilise `execute_write_sql`.\n"
        "Tu es également un assistant IA général : s'il te plaît, réponds avec plaisir à TOUTES les autres questions générales de l'utilisateur (culture générale, calculs, traductions, rédactions, questions diverses, aide, etc.) même si elles ne concernent pas directement FABOuanes. Si une question requiert un accès à internet en temps réel (comme la météo en direct), explique-le poliment mais réponds sur tout le reste au mieux de tes connaissances.\n"
        "Règles STRICTES :\n"
        "1. Ne modifie les données que si l'utilisateur te le demande explicitement.\n"
        "2. Ne lis ou ne modifie jamais la table 'users' (contient les mots de passe hachés).\n"
        "3. Ne fais jamais d'opérations DROP ou ALTER sur les tables."
    )
    
    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    max_retries = 4
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                logger.warning("Quota ou Rate Limit 429 de l'API Gemini atteint. Nouvelle tentative dans %ds...", wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception:
            raise

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
            return f"Désolé, impossible de joindre l'API Gemini ({str(exc)}). Vérifiez votre clé d'API dans les paramètres."

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
            elif func_name == "execute_write_sql":
                sql_query = func_args.get("query", "")
                output = execute_write_sql(sql_query)
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
