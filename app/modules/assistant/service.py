import os
import json
import logging
import asyncio
import httpx
from typing import Any, Dict, List
from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant")

TABLE_SCHEMAS = {
    "clients": (
        "id* (BIGINT auto), name* (TEXT), phone (TEXT), address (TEXT), notes (TEXT), "
        "opening_credit* (NUMERIC défaut 0), credit_limit (NUMERIC), created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Liste des clients. "
        "IMPORTANT: Avant INSERT une vente ou versement, vérifier que le client existe via SELECT id, name FROM clients."
    ),
    "suppliers": (
        "id* (BIGINT auto), name* (TEXT), phone (TEXT), address (TEXT), notes (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Liste des fournisseurs. "
        "IMPORTANT: Avant INSERT un achat, vérifier que le fournisseur existe via SELECT id, name FROM suppliers."
    ),
    "raw_materials": (
        "id* (BIGINT auto), name* (TEXT), unit* (TEXT), stock_qty* (NUMERIC), avg_cost* (NUMERIC), "
        "sale_price* (NUMERIC), alert_threshold* (NUMERIC), threshold_qty* (NUMERIC), updated_at (TIMESTAMPTZ) "
        "— Matières premières en stock. "
        "IMPORTANT: Avant INSERT un achat ou vente de matière, vérifier que la matière existe via SELECT id, name, unit FROM raw_materials."
    ),
    "finished_products": (
        "id* (BIGINT auto), name* (TEXT), default_unit* (TEXT), stock_qty* (NUMERIC), "
        "sale_price* (NUMERIC), avg_cost* (NUMERIC), alert_threshold* (NUMERIC), updated_at (TIMESTAMPTZ) "
        "— Produits finis en stock. "
        "IMPORTANT: Avant INSERT une vente de produit fini, vérifier que le produit existe via SELECT id, name, avg_cost, sale_price FROM finished_products."
    ),
    "purchases": (
        "id* (BIGINT auto), supplier_id (INTEGER FK→suppliers), document_id (INTEGER), "
        "raw_material_id (INTEGER FK→raw_materials), finished_product_id (BIGINT FK→finished_products), "
        "quantity* (NUMERIC), unit* (TEXT défaut 'kg'), unit_price* (NUMERIC), total* (NUMERIC), "
        "purchase_date* (DATE), notes (TEXT), custom_item_name (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Achats (matières premières ou produits finis). "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT (auto-généré). "
        "Il faut OBLIGATOIREMENT soit raw_material_id soit finished_product_id (sinon la ligne n'apparaît pas). "
        "Étapes pour créer un achat: "
        "1) SELECT id,name FROM suppliers; "
        "2) SELECT id,name FROM raw_materials (ou finished_products); "
        "3) INSERT INTO purchases (supplier_id, raw_material_id, quantity, unit, unit_price, total, purchase_date) VALUES (...); "
        "4) UPDATE raw_materials SET stock_qty = stock_qty + [quantity], avg_cost = [unit_price] WHERE id = [id];"
    ),
    "sales": (
        "id* (BIGINT auto), client_id (INTEGER FK→clients), document_id (INTEGER), "
        "finished_product_id* (INTEGER FK→finished_products — OBLIGATOIRE, pas NULL !), quantity* (NUMERIC), unit* (TEXT), "
        "unit_price* (NUMERIC), total* (NUMERIC), sale_type* (TEXT: 'cash' si payé immédiatement, 'credit' si paiement différé), "
        "amount_paid* (NUMERIC: = total si cash, = acompte si credit, = 0 si rien payé), "
        "balance_due* (NUMERIC: = 0 si cash, = total - amount_paid si credit), "
        "cost_price_snapshot* (NUMERIC: = avg_cost du produit au moment de la vente — lire dans finished_products.avg_cost), "
        "profit_amount* (NUMERIC: = (unit_price - cost_price_snapshot) * quantity), "
        "sale_date* (DATE), notes (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Ventes de produits finis. "
        "RÈGLE ABSOLUE: finished_product_id ne peut PAS être NULL — sinon la ligne n'apparaît PAS dans les opérations. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT. "
        "Étapes pour créer une vente de produit fini: "
        "1) SELECT id,name FROM clients WHERE lower(name) LIKE '%nom%'; "
        "2) SELECT id,name,sale_price,avg_cost,stock_qty,default_unit FROM finished_products WHERE lower(name) LIKE '%produit%'; "
        "3) INSERT INTO sales (client_id, finished_product_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date) VALUES (...); "
        "4) UPDATE finished_products SET stock_qty = stock_qty - [quantity] WHERE id = [id];"
    ),
    "raw_sales": (
        "id* (BIGINT auto), client_id (INTEGER FK→clients), document_id (INTEGER), "
        "raw_material_id* (INTEGER FK→raw_materials — OBLIGATOIRE, pas NULL !), quantity* (NUMERIC), unit* (TEXT), "
        "unit_price* (NUMERIC), total* (NUMERIC), sale_type* (TEXT: 'cash' ou 'credit'), "
        "amount_paid* (NUMERIC), balance_due* (NUMERIC), cost_price_snapshot* (NUMERIC: avg_cost de la matière), "
        "profit_amount* (NUMERIC: = (unit_price - cost_price_snapshot) * quantity), "
        "sale_date* (DATE), notes (TEXT), custom_item_name (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Ventes de matières premières. "
        "RÈGLE ABSOLUE: raw_material_id ne peut PAS être NULL — sinon la ligne n'apparaît PAS dans les opérations. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT. "
        "Étapes pour créer une vente de matière première: "
        "1) SELECT id,name FROM clients WHERE lower(name) LIKE '%nom%'; "
        "2) SELECT id,name,sale_price,avg_cost,stock_qty,unit FROM raw_materials WHERE lower(name) LIKE '%matière%'; "
        "3) INSERT INTO raw_sales (client_id, raw_material_id, quantity, unit, unit_price, total, sale_type, amount_paid, balance_due, cost_price_snapshot, profit_amount, sale_date) VALUES (...); "
        "4) UPDATE raw_materials SET stock_qty = stock_qty - [quantity] WHERE id = [id];"
    ),
    "payments": (
        "id* (BIGINT auto), client_id* (INTEGER FK→clients — OBLIGATOIRE, pas NULL !), "
        "sale_id (INTEGER FK→sales optionnel), "
        "raw_sale_id (INTEGER FK→raw_sales optionnel), "
        "sale_kind (TEXT: 'finished' si lié à une vente produit fini, 'raw' si lié à une vente matière première, NULL si versement général), "
        "payment_type* (TEXT: TOUJOURS 'versement' pour un versement client, ou 'avance' pour une avance — NE JAMAIS mettre 'cash', 'cheque' ou 'virement' ici !), "
        "allocation_meta (TEXT JSON optionnel), amount* (NUMERIC), payment_date* (DATE), notes (TEXT), "
        "created_at* (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Paiements/versements reçus des clients. "
        "RÈGLE ABSOLUE: client_id ne peut PAS être NULL — sinon la ligne n'apparaît PAS. "
        "RÈGLE ABSOLUE: payment_type doit être 'versement' ou 'avance' — jamais autre chose. "
        "RÈGLE ABSOLUE: Ne PAS spécifier 'id' dans INSERT. "
        "Étapes pour créer un versement: "
        "1) SELECT id,name FROM clients WHERE lower(name) LIKE '%nom%'; "
        "2) INSERT INTO payments (client_id, payment_type, amount, payment_date) VALUES ([id], 'versement', [montant], CURRENT_DATE);"
    ),
    "expenses": (
        "id* (BIGINT auto), date* (DATE), category* (TEXT), description (TEXT), "
        "amount* (NUMERIC), payment_method (TEXT), "
        "created_at (TIMESTAMPTZ auto), updated_at (TIMESTAMPTZ) "
        "— Dépenses et charges. "
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT."
    ),
    "production_batches": (
        "id* (BIGINT auto), finished_product_id* (INTEGER FK→finished_products), "
        "output_quantity* (NUMERIC), production_cost* (NUMERIC), unit_cost* (NUMERIC), "
        "production_date* (DATE), notes (TEXT) "
        "— Lots de production de produits finis. "
        "RÈGLE: Ne PAS spécifier 'id' dans INSERT."
    ),
    "production_batch_items": (
        "id* (BIGINT auto), batch_id* (INTEGER FK→production_batches), "
        "raw_material_id* (INTEGER FK→raw_materials), quantity* (NUMERIC), "
        "unit_cost_snapshot* (NUMERIC), line_cost* (NUMERIC) "
        "— Matières premières consommées par lot de production"
    ),
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
            # pg8000 CompatCursor n'a pas toujours 'rowcount' — on utilise getattr pour éviter l'erreur
            rowcount = getattr(cur, "rowcount", None)
            try:
                cur.close()
            except Exception:
                pass
            if rowcount is not None:
                return {"success": True, "rowcount": rowcount, "message": f"{rowcount} ligne(s) affectée(s)."}
            else:
                return {"success": True, "message": "Opération exécutée avec succès."}
    except Exception as e:
        return {"error": f"Erreur SQL lors de l'écriture : {str(e)}"}

async def call_gemini_api(contents: List[Dict[str, Any]], api_key: str, model_name: str = "gemini-flash-latest") -> Dict[str, Any]:
    """Appelle l'API Gemini avec les messages et outils définis."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    # Schéma intégré directement dans le prompt pour éviter un appel get_schema inutile
    schema_text = "\n".join(f"- {t}: {d}" for t, d in TABLE_SCHEMAS.items())
    
    tools = [
        {
            "functionDeclarations": [
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
                    "description": "Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour ajouter, modifier ou supprimer des données.",
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
        f"Tu fonctionnes actuellement avec le modèle : **{model_name}** (Google Gemini).\n"
        "Si on te demande quel modèle tu utilises, réponds avec ce nom.\n"
        "Tu as un accès direct à la base de données via des outils SQL.\n"
        "Tu comprends parfaitement le français, l'anglais, l'arabe (dialecte algérien/darja) et le kabyle (Taqbaylit).\n"
        "Rédige tes réponses de manière claire et professionnelle dans la langue choisie par l'utilisateur (français par défaut).\n"
        "Utilise le formatage Markdown (tableaux, listes, gras) pour rendre les données lisibles.\n\n"
        f"SCHÉMA DE LA BASE DE DONNÉES (utilise-le directement sans appeler get_schema) :\n{schema_text}\n\n"
        f"{app_routes}\n"
        "Pour LIRE des données → utilise `execute_readonly_sql`.\n"
        "Pour AJOUTER, MODIFIER ou SUPPRIMER des données → utilise `execute_write_sql` uniquement si l'utilisateur le demande explicitement.\n"
        "Quand l'utilisateur veut naviguer vers une section, donne-lui le lien sous forme de chemin (ex: /operations/payments/new).\n"
        "Tu es aussi un assistant général : réponds à TOUTES les questions (culture générale, calculs, traductions, aide…) même hors FABOuanes.\n"
        "Règles STRICTES :\n"
        "1. Ne modifie les données que sur demande explicitement.\n"
        "2. N'accède jamais à la table 'users'.\n"
        "3. N'exécute jamais DROP, ALTER ou TRUNCATE."
    )
    
    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    max_retries = 2
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=60.0)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 1.5
                logger.warning("Rate Limit 429 sur %s. Attente de 1.5s avant nouvel essai...", model_name)
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception:
            raise


OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"

async def is_ollama_available() -> bool:
    """Vérifie si le serveur Ollama local est actif."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
            return r.status_code == 200
    except Exception:
        return False

async def run_ollama_agent(messages: List[Dict[str, Any]], schema_text: str) -> str:
    """
    Boucle d'agent complète avec Ollama local (qwen2.5:7b).
    Supporte le tool calling natif OpenAI : execute_readonly_sql + execute_write_sql.
    Peut lire et écrire la base de données, exactement comme Gemini.
    """
    app_routes_ollama = (
        "PAGES ET CHEMINS DE L'APPLICATION :\n"
        "- Tableau de bord → /dashboard\n"
        "- Clients → /contacts/clients | Nouveau client → /contacts/clients/new | Fiche client → /contacts/clients/{id}\n"
        "- Fournisseurs → /contacts/suppliers | Nouveau → /contacts/suppliers/new\n"
        "- Opérations → /operations | Nouvelle vente → /operations/sales/new\n"
        "- Nouvel achat → /operations/purchases/new | Nouveau versement → /operations/payments/new\n"
        "- Catalogue/Stock → /catalog | Produits finis → /products | Matières premières → /raw-materials\n"
        "- Production → /production | Nouveau lot → /production/new\n"
        "- Dépenses → /expenses | Nouvelle dépense → /expenses/new\n"
        "- Rapports → /reports | Paramètres/Admin → /admin | Utilisateurs → /users\n"
        "- Journal d'audit → /admin/audit | Notes → /notes | Bons/PDF → /bons\n"
    )

    system_prompt = (
        "Tu es l'Assistant IA de FABOuanes, un progiciel de gestion commerciale et de stock.\n"
        f"Tu fonctionnes actuellement avec le modèle : **{OLLAMA_MODEL}** (IA locale Ollama).\n"
        "Si on te demande quel modèle tu utilises, réponds avec ce nom.\n"
        "Tu comprends parfaitement le français, l'anglais, l'arabe (darja) et le kabyle.\n"
        "Réponds dans la langue utilisée par l'utilisateur (français par défaut).\n"
        "Utilise le Markdown pour formater les réponses (tableaux, listes, gras).\n\n"
        f"SCHÉMA DE LA BASE DE DONNÉES :\n{schema_text}\n\n"
        f"{app_routes_ollama}\n"
        "Pour LIRE des données → utilise execute_readonly_sql.\n"
        "Pour CRÉER, MODIFIER ou SUPPRIMER des données → utilise execute_write_sql "
        "uniquement si l'utilisateur le demande explicitement.\n"
        "Quand l'utilisateur veut naviguer vers une section, donne-lui le chemin (ex: /operations/payments/new).\n"
        "Réponds à TOUTES les questions (générales, calculs, traductions, etc.).\n"
        "Règles : N'accède jamais à la table 'users'. N'exécute jamais DROP, ALTER ou TRUNCATE."
    )

    # Outils en format OpenAI (compatible Ollama)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_readonly_sql",
                "description": "Exécute une requête SQL SELECT en lecture seule et retourne les résultats.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "La requête SQL SELECT complète à exécuter."
                        }
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_write_sql",
                "description": "Exécute une requête SQL d'écriture (INSERT, UPDATE, DELETE) pour ajouter, modifier ou supprimer des données.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "La requête SQL complète (INSERT, UPDATE ou DELETE)."
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    ]

    # Convertir l'historique Gemini → format OpenAI/Ollama
    ollama_messages = [{"role": "system", "content": system_prompt}]
    for msg in messages:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        if role in ("user", "model"):
            text = " ".join(p.get("text", "") for p in parts if "text" in p)
            if text.strip():
                ollama_messages.append({
                    "role": "assistant" if role == "model" else "user",
                    "content": text
                })

    max_turns = 5
    for turn in range(max_turns):
        payload = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 2048}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    timeout=180.0  # CPU peut être lent
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            logger.error("Erreur Ollama tour %d : %s", turn, e)
            return f"⚠️ Erreur IA locale (Ollama) : {str(e)}"

        message = data.get("message", {})
        tool_calls = message.get("tool_calls", [])
        content = message.get("content", "")

        # Ajouter la réponse de l'assistant à l'historique
        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        ollama_messages.append(assistant_msg)

        if not tool_calls:
            # Réponse textuelle finale
            return content if content.strip() else "Pas de réponse."

        # Exécuter les appels d'outils
        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            # Ollama peut retourner arguments en str ou dict
            raw_args = func.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    func_args = json.loads(raw_args)
                except Exception:
                    func_args = {}
            else:
                func_args = raw_args

            logger.info("Ollama Agent Call: '%s' args=%s", func_name, func_args)

            if func_name == "execute_readonly_sql":
                output = execute_readonly_sql(func_args.get("query", ""))
            elif func_name == "execute_write_sql":
                output = execute_write_sql(func_args.get("query", ""))
            else:
                output = {"error": f"Outil '{func_name}' inconnu."}

            # Ajouter le résultat de l'outil dans la conversation
            ollama_messages.append({
                "role": "tool",
                "content": json.dumps(output, ensure_ascii=False, default=str)
            })

    return "La requête Ollama a dépassé la limite de tours sans retourner de réponse."


async def run_assistant_agent(messages: List[Dict[str, Any]], api_key: str) -> str:
    """Orchestre la boucle d'agent avec Gemini (Tool Calling)."""
    # Copie locale de l'historique pour l'échange en cours
    contents = list(messages)
    
    # Limite de sécurité sur le nombre de tours d'appels d'outils successifs
    # 5 tours = assez pour les opérations complexes (créer vente, chercher client, INSERT...)
    # sans gaspiller trop de quota API
    max_turns = 5
    for turn in range(max_turns):
        res = None
        last_exception = None
        candidate_models = ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-flash-latest"]
        for model in candidate_models:
            try:
                res = await call_gemini_api(contents, api_key, model_name=model)
                break
            except httpx.HTTPStatusError as exc:
                last_exception = exc
                status = exc.response.status_code
                logger.warning("Modèle %s erreur HTTP %s. Essai du modèle suivant...", model, status)
                continue
            except Exception as exc:
                last_exception = exc
                logger.warning("Erreur avec le modèle %s : %s. Essai du modèle suivant...", model, exc)
                continue
                
        if res is None:
            # Tous les modèles Gemini ont échoué → essai du fallback Ollama local
            logger.warning("Tous les modèles Gemini ont échoué. Tentative avec Ollama local...")
            schema_text = "\n".join(f"- {t}: {d}" for t, d in TABLE_SCHEMAS.items())
            ollama_ok = await is_ollama_available()
            if ollama_ok:
                try:
                    ollama_response = await run_ollama_agent(contents, schema_text)
                    logger.info("Réponse obtenue via Ollama local.")
                    return f"🤖 **(Mode IA locale - Ollama)**\n\n{ollama_response}"
                except Exception as ollama_exc:
                    logger.error("Ollama local a également échoué : %s", ollama_exc)
                    return (
                        "⚠️ Les modèles Gemini sont saturés et Ollama local a échoué.\n"
                        "Réessayez dans quelques minutes."
                    )
            else:
                error_msg = str(last_exception) if last_exception else "Quota dépassé."
                return (
                    f"⚠️ Quota Gemini dépassé ({error_msg}).\n"
                    "💬 **Conseil :** Ollama n'est pas démarré. "
                    "Lancez l'application **Ollama** pour continuer sans internet."
                )


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
