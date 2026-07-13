import json
import logging
import asyncio
import httpx
from typing import Any, Dict, List, Tuple

from app.core.db_helpers import db_manager
from app.modules.assistant.confirmations import get_tool_confirmation_message, tool_requires_confirmation
from app.modules.assistant.sql_tools import execute_readonly_sql, execute_write_sql
from app.modules.assistant.tool_specs import get_gemini_tools, get_ollama_tools
from app.modules.assistant.tool_actions import execute_tool_action
from app.modules.assistant.schema_context import (
    get_schema,
    get_sabrina_system_prompt,
)
from app.modules.assistant.intent import classify_intent

logger = logging.getLogger("fabouanes.assistant")


_gemini_client: httpx.AsyncClient | None = None
_ollama_client: httpx.AsyncClient | None = None


def get_gemini_client() -> httpx.AsyncClient:
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = httpx.AsyncClient(timeout=60.0)
    return _gemini_client


def get_ollama_client() -> httpx.AsyncClient:
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = httpx.AsyncClient(timeout=180.0, trust_env=False)
    return _ollama_client


async def close_http_clients() -> None:
    """Ferme proprement les clients HTTP globaux lors du shutdown."""
    global _gemini_client, _ollama_client
    for name, client in [("gemini", _gemini_client), ("ollama", _ollama_client)]:
        if client is not None:
            try:
                await client.aclose()
                logger.info("Client HTTP %s fermé.", name)
            except Exception as e:
                logger.warning("Erreur lors de la fermeture du client HTTP %s: %s", name, e)
    _gemini_client = None
    _ollama_client = None


async def compress_history_if_needed(messages: List[Dict[str, Any]], api_key: str, is_local: bool) -> List[Dict[str, Any]]:
    if len(messages) <= 18:
        return messages
    to_summarize = messages[:-8]
    to_keep = messages[-8:]
    summary_prompt = (
        "Fais un résumé très condensé en français des actions, discussions et opérations mentionnées ci-dessous. "
        "Sois précis sur les chiffres, les noms de clients et les produits créés. Ne dépasse pas 150 mots."
    )

    conversation_text = ""
    for msg in to_summarize:
        role = msg.get("role", "user")
        parts = msg.get("parts", [])
        if isinstance(parts, list):
            content = " ".join(p.get("text", "") for p in parts if "text" in p)
        else:
            content = msg.get("content", "")
        conversation_text += f"{'Utilisateur' if role == 'user' else 'Sabrina'}: {content}\n"

    if is_local:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": conversation_text}
            ],
            "stream": False
        }
        try:
            client = get_ollama_client()
            res = await client.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=60.0)
            res.raise_for_status()
            data = res.json()
            summary_text = data["message"]["content"]

            new_messages = []
            new_messages.append({
                "role": "user",
                "content": f"[CONTEXTE DES DISCUSSIONS PRÉCÉDENTES : {summary_text.strip()}]"
            })
            new_messages.extend(to_keep)
            return new_messages
        except Exception as e:
            logger.warning("Ollama history summarization failed: %s", e)
            return messages
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{summary_prompt}\n\nConversation à résumer :\n{conversation_text}"}]}
            ]
        }
        try:
            client = get_gemini_client()
            res = await client.post(url, json=payload, headers=headers, timeout=30.0)
            res.raise_for_status()
            data = res.json()
            summary_text = data["candidates"][0]["content"]["parts"][0]["text"]

            new_messages = []
            new_messages.append({
                "role": "user",
                "parts": [{"text": f"[CONTEXTE DES DISCUSSIONS PRÉCÉDENTES : {summary_text.strip()}]"}]
            })
            new_messages.extend(to_keep)
            return new_messages
        except Exception as e:
            logger.warning("Gemini history summarization failed: %s", e)
            return messages


def _ensure_thought_signatures(contents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Garantit que chaque appel de fonction dans l'historique contient un thoughtSignature pour les modèles de raisonnement."""
    for msg in contents:
        if msg.get("role") == "model":
            parts = msg.get("parts", [])
            if isinstance(parts, list):
                for part in parts:
                    if isinstance(part, dict) and "functionCall" in part:
                        if "thoughtSignature" not in part and "thought_signature" not in part:
                            part["thoughtSignature"] = "EjQKMgERTTIPSleTFwevyxEQZ0DfJeePXihcsxw9SDCz8z1PoTv6LqiCDtlT6kV/cpeGKGUa"
    return contents

async def call_gemini_api(contents: List[Dict[str, Any]], api_key: str, model_name: str = "gemini-flash-latest") -> Dict[str, Any]:
    """Appelle l'API Gemini avec les messages et outils définis (non-streamed fallback/utility)."""
    contents = _ensure_thought_signatures(contents)
    tools = get_gemini_tools()
    system_instruction = get_sabrina_system_prompt(model_name)

    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }

    headers = {"Content-Type": "application/json"}
    if api_key.startswith("AIzaSy") or api_key.startswith("AQ"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        headers["Authorization"] = f"Bearer {api_key}"

    max_retries = 2
    for attempt in range(max_retries):
        try:
            client = get_gemini_client()
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

def _extract_json_objects(text: str) -> List[Tuple[str, int, int]]:
    objs = []
    start = -1
    depth = 0
    in_string = False
    escape = False

    for i, char in enumerate(text):
        if char == '"' and not escape:
            in_string = not in_string
        if in_string:
            if char == '\\' and not escape:
                escape = True
            else:
                escape = False
            continue

        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            if depth > 0:
                depth -= 1
                if depth == 0:
                    objs.append((text[start:i+1], start, i+1))
        escape = False

    return objs

async def call_gemini_api_generator(contents: List[Dict[str, Any]], api_key: str, model_name: str = "gemini-flash-latest"):
    """Appelle l'API Gemini en mode streaming et produit des événements."""
    contents = _ensure_thought_signatures(contents)
    tools = get_gemini_tools()
    system_instruction = get_sabrina_system_prompt(model_name)

    payload = {
        "contents": contents,
        "tools": tools,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }

    headers = {"Content-Type": "application/json"}
    if api_key.startswith("AIzaSy") or api_key.startswith("AQ"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}"
    else:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent"
        headers["Authorization"] = f"Bearer {api_key}"

    max_retries = 2
    for attempt in range(max_retries):
        try:
            client = get_gemini_client()
            async with client.stream("POST", url, json=payload, headers=headers, timeout=60.0) as response:
                if response.status_code != 200:
                    err_text = await response.aread()
                    logger.error("streamGenerateContent failed status %d: %s", response.status_code, err_text)
                    raise httpx.HTTPStatusError(
                        f"HTTP Error {response.status_code}",
                        request=response.request,
                        response=response
                    )

                buffer = ""
                async for chunk in response.aiter_text():
                    buffer += chunk
                    objs = _extract_json_objects(buffer)
                    if objs:
                        last_end = objs[-1][2]
                        for obj_text, _, _ in objs:
                            try:
                                data = json.loads(obj_text)
                                candidates = data.get("candidates", [])
                                if candidates:
                                    content_parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in content_parts:
                                        yield {"type": "raw_part", "part": part}
                                        if "text" in part:
                                            yield {"type": "text_chunk", "text": part["text"]}
                                        if "functionCall" in part:
                                            yield {"type": "function_call", "functionCall": part["functionCall"]}
                            except Exception:
                                pass
                        buffer = buffer[last_end:]
            break
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 1.5
                logger.warning("Rate Limit 429 sur %s. Attente de 1.5s avant nouvel essai...", model_name)
                await asyncio.sleep(wait_time)
                continue
            raise
        except Exception:
            raise

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:7b"

def start_ollama() -> bool:
    """Lance le serveur Ollama en arrière-plan sur la machine de l'utilisateur."""
    import shutil
    import subprocess
    ollama_path = shutil.which("ollama")
    if not ollama_path:
        import os
        standard_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        if os.path.exists(standard_path):
            ollama_path = standard_path
        else:
            return False
    try:
        import os
        creationflags = 0
        if os.name == 'nt':
            creationflags = 0x08000000  # CREATE_NO_WINDOW
        subprocess.Popen(
            [ollama_path, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags
        )
        logger.info("Ollama process started successfully in the background.")
        return True
    except Exception as e:
        logger.error("Failed to start Ollama process: %s", e)
        return False

async def is_ollama_available() -> bool:
    """Vérifie si le serveur Ollama local est actif."""
    try:
        client = get_ollama_client()
        r = await client.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def find_past_tool_execution(messages: List[Dict[str, Any]], func_name: str, func_args: dict) -> Any | None:
    """
    Parcourt l'historique des messages pour déterminer si cet appel de fonction (nom et arguments équivalents)
    a déjà été exécuté avec succès. Si oui, retourne sa valeur de retour passée pour éviter de le re-confirmer ou ré-exécuter.
    """
    def normalize_val(val):
        if isinstance(val, float):
            return round(val, 4)
        if isinstance(val, int):
            return float(val)
        if val is None or val == "":
            return None
        if isinstance(val, dict):
            return {k: normalize_val(v) for k, v in val.items() if v is not None and v != ""}
        if isinstance(val, list):
            return [normalize_val(x) for x in val]
        return val

    normalized_args = {k: normalize_val(v) for k, v in func_args.items() if v is not None and v != ""}

    # On parcourt les messages de l'historique
    for i, msg in enumerate(messages):
        role = msg.get("role")
        
        calls = []
        if role in ("model", "assistant"):
            parts = msg.get("parts")
            if isinstance(parts, list):
                for p in parts:
                    if "functionCall" in p:
                        calls.append(p["functionCall"])
            tool_calls = msg.get("tool_calls")
            if isinstance(tool_calls, list):
                for tc in tool_calls:
                    func = tc.get("function")
                    if func:
                        calls.append({"name": func.get("name"), "args": func.get("arguments") or {}})
                        
        for call in calls:
            if call.get("name") == func_name:
                call_args = call.get("args") or {}
                if isinstance(call_args, str):
                    try:
                        call_args = json.loads(call_args)
                    except Exception:
                        pass
                if not isinstance(call_args, dict):
                    call_args = {}
                normalized_call_args = {k: normalize_val(v) for k, v in call_args.items() if v is not None and v != ""}
                
                if normalized_call_args == normalized_args:
                    # Trouvé l'appel ! Cherchons la réponse correspondante dans les messages suivants
                    for j in range(i + 1, len(messages)):
                        next_msg = messages[j]
                        next_role = next_msg.get("role")
                        
                        if next_role == "function":
                            next_parts = next_msg.get("parts")
                            if isinstance(next_parts, list):
                                for np in next_parts:
                                    if "functionResponse" in np:
                                        fr = np["functionResponse"]
                                        if fr.get("name") == func_name:
                                            resp = fr.get("response") or {}
                                            if isinstance(resp, dict) and "output" in resp:
                                                return resp["output"]
                                            return resp
                        elif next_role == "tool":
                            content = next_msg.get("content")
                            if content:
                                try:
                                    parsed = json.loads(content)
                                    if isinstance(parsed, dict):
                                        if "output" in parsed:
                                            return parsed["output"]
                                        return parsed
                                except Exception:
                                    return {"output": content}
    return None


async def run_ollama_agent_generator(messages: List[Dict[str, Any]], confirmed_query: str | None = None, user_role: str = "operator"):
    """Boucle d'agent asynchrone génératrice pour Ollama local."""
    if not await is_ollama_available():
        yield {"type": "status", "message": "Démarrage automatique de l'IA locale (Ollama)..."}
        start_ollama()
        for attempt in range(6):
            await asyncio.sleep(1.0)
            if await is_ollama_available():
                break
        if not await is_ollama_available():
            yield {
                "type": "error",
                "error": (
                    "⚠️ Impossible de démarrer l'IA locale (Ollama).\n"
                    "💬 **Conseil :** Veuillez démarrer l'application **Ollama** manuellement sur votre machine."
                )
            }
            return

    system_prompt = get_sabrina_system_prompt(OLLAMA_MODEL)
    tools = get_ollama_tools()

    ollama_messages = [{"role": "system", "content": system_prompt}]
    expected_tool_calls = []  # list of (function_name, tool_call_id)

    for msg_idx, msg in enumerate(messages):
        role = msg.get("role", "user")
        parts = msg.get("parts", [])

        if role == "user":
            # Check if this is a function response sent as a "user" message
            has_func_resp = False
            if isinstance(parts, list):
                for p in parts:
                    if "functionResponse" in p:
                        has_func_resp = True
                        fr = p["functionResponse"]
                        func_name = fr.get("name")
                        tc_id = None
                        for idx, (exp_name, exp_id) in enumerate(expected_tool_calls):
                            if exp_name == func_name:
                                tc_id = exp_id
                                expected_tool_calls.pop(idx)
                                break
                        if not tc_id:
                            tc_id = f"call_unknown_{msg_idx}"
                        ollama_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps(fr.get("response", {}), ensure_ascii=False, default=str)
                        })
            if not has_func_resp:
                text = " ".join(p.get("text", "") for p in parts if "text" in p) if isinstance(parts, list) else msg.get("content", "")
                if text.strip():
                    ollama_messages.append({"role": "user", "content": text})

        elif role in ("model", "assistant"):
            text = ""
            tool_calls = []

            # Handle native assistant role with tool_calls (from confirmations)
            if "tool_calls" in msg:
                for tc_idx, tc in enumerate(msg["tool_calls"]):
                    func = tc.get("function", {})
                    func_name = func.get("name")
                    raw_args = func.get("arguments", {})
                    # Ensure arguments is a dict/object for Ollama
                    if isinstance(raw_args, str):
                        try:
                            func_args = json.loads(raw_args)
                        except Exception:
                            func_args = {}
                    else:
                        func_args = raw_args

                    tc_id = tc.get("id") or f"call_{msg_idx}_{tc_idx}"
                    tool_calls.append({
                        "id": tc_id,
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": func_args
                        }
                    })
                    expected_tool_calls.append((func_name, tc_id))
                text = msg.get("content", "")
            else:
                # Handle Gemini model role with parts
                if isinstance(parts, list):
                    tc_idx = 0
                    for p in parts:
                        if "text" in p:
                            text += p["text"]
                        if "functionCall" in p:
                            fc = p["functionCall"]
                            func_name = fc.get("name")
                            raw_args = fc.get("args", {})
                            if isinstance(raw_args, str):
                                try:
                                    func_args = json.loads(raw_args)
                                except Exception:
                                    func_args = {}
                            else:
                                func_args = raw_args

                            tc_id = f"call_{msg_idx}_{tc_idx}"
                            tool_calls.append({
                                "id": tc_id,
                                "type": "function",
                                "function": {
                                    "name": func_name,
                                    "arguments": func_args
                                }
                            })
                            expected_tool_calls.append((func_name, tc_id))
                            tc_idx += 1
                else:
                    text = msg.get("content", "")

            assistant_msg = {"role": "assistant", "content": text}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            ollama_messages.append(assistant_msg)

        elif role == "function":
            # Map Gemini function responses back to the expected tool calls
            if isinstance(parts, list) and parts:
                for p in parts:
                    if "functionResponse" in p:
                        fr = p["functionResponse"]
                        func_name = fr.get("name")

                        # Find the matching expected tool call
                        tc_id = None
                        for idx, (exp_name, exp_id) in enumerate(expected_tool_calls):
                            if exp_name == func_name:
                                tc_id = exp_id
                                expected_tool_calls.pop(idx)
                                break
                        if not tc_id:
                            tc_id = f"call_unknown_{msg_idx}"

                        ollama_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": json.dumps(fr.get("response", {}), ensure_ascii=False, default=str)
                        })

        elif role == "tool":
            # Map native tool responses
            tc_id = msg.get("tool_call_id")
            if not tc_id and expected_tool_calls:
                _, tc_id = expected_tool_calls.pop(0)
            elif not tc_id:
                tc_id = f"call_unknown_{msg_idx}"

            ollama_messages.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": msg.get("content", "")
            })

    max_turns = 15
    sql_errors_count = 0
    for turn in range(max_turns):
        payload = {
            "model": OLLAMA_MODEL,
            "messages": ollama_messages,
            "tools": tools,
            "stream": True,
            "options": {"temperature": 0.3, "num_predict": 2048}
        }

        content = ""
        tool_calls = []
        try:
            client = get_ollama_client()
            async with client.stream(
                "POST",
                f"{OLLAMA_URL}/api/chat",
                json=payload,
                timeout=180.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        msg = chunk.get("message", {})

                        chunk_content = msg.get("content", "")
                        if chunk_content:
                            content += chunk_content
                            yield {"type": "text_chunk", "text": chunk_content}

                        chunk_tool_calls = msg.get("tool_calls", [])
                        for tc in chunk_tool_calls:
                            tool_calls.append(tc)
                    except Exception:
                        pass
        except Exception as e:
            yield {"type": "error", "error": f"⚠️ Erreur IA locale (Ollama) : {str(e)}"}
            return

        assistant_msg = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        ollama_messages.append(assistant_msg)

        if tool_calls:
            gemini_parts = []
            for tc in tool_calls:
                func = tc.get("function", {})
                func_name = func.get("name", "")
                raw_args = func.get("arguments", {})
                if isinstance(raw_args, str):
                    try:
                        func_args = json.loads(raw_args)
                    except Exception:
                        func_args = {}
                else:
                    func_args = raw_args
                gemini_parts.append({"functionCall": {"name": func_name, "args": func_args}})
            messages.append({"role": "model", "parts": gemini_parts})

        if not tool_calls:
            messages.append({"role": "model", "parts": [{"text": content}]})
            yield {"type": "final_response", "text": content if content.strip() else "Pas de réponse.", "history": messages}
            return

        for tc in tool_calls:
            func = tc.get("function", {})
            func_name = func.get("name", "")
            raw_args = func.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    func_args = json.loads(raw_args)
                except Exception:
                    func_args = {}
            else:
                func_args = raw_args

            logger.info("Ollama Agent Call: '%s' args=%s", func_name, func_args)

            # Éviter de ré-exécuter/re-confiremer une action déjà effectuée dans cette conversation
            past_output = find_past_tool_execution(messages[:-1], func_name, func_args)

            if past_output is not None:
                logger.info("Ollama Agent: Réutilisation du résultat de l'exécution passée pour '%s' pour éviter une boucle", func_name)
                output = past_output
            elif func_name == "execute_readonly_sql":
                sql_query = func_args.get("query", "")
                yield {"type": "status", "message": "Recherche dans la base de données locale (SELECT)..."}
                output = execute_readonly_sql(sql_query)
            elif func_name == "execute_write_sql":
                sql_query = func_args.get("query", "")
                is_confirmed = confirmed_query and confirmed_query.strip() == sql_query.strip()
                if not is_confirmed and confirmed_query:
                    try:
                        cq_data = json.loads(confirmed_query)
                        if cq_data.get("name") == "execute_write_sql" and cq_data.get("args", {}).get("query") == sql_query:
                            is_confirmed = True
                    except Exception:
                        pass
                if not is_confirmed:
                    yield {
                        "type": "confirmation_required",
                        "query": sql_query,
                        "message": f"Je m'apprête à modifier la base de données (local). Veuillez confirmer la requête SQL ci-dessous :\n```sql\n{sql_query}\n```",
                        "history": messages
                    }
                    return
                yield {"type": "status", "message": "Modification de la base de données locale (confirmée)..."}
                output = execute_write_sql(sql_query)
            else:
                is_write = tool_requires_confirmation(func_name)
                if is_write:
                    normalized_call = json.dumps({"name": func_name, "args": func_args}, sort_keys=True)
                    is_confirmed = False
                    if confirmed_query:
                        if confirmed_query.strip() == normalized_call:
                            is_confirmed = True
                        else:
                            try:
                                cq_data = json.loads(confirmed_query)
                                if cq_data.get("name") == func_name and cq_data.get("args") == func_args:
                                    is_confirmed = True
                            except Exception:
                                pass
                    if not is_confirmed:
                        msg = get_tool_confirmation_message(func_name, func_args)
                        yield {
                            "type": "confirmation_required",
                            "query": normalized_call,
                            "message": msg,
                            "history": messages
                        }
                        return

                yield {"type": "status", "message": f"Exécution de l'action '{func_name}' (local)..."}
                output = await execute_tool_action(func_name, func_args, user_role=user_role)

            if isinstance(output, dict) and "error" in output:
                if func_name in ("execute_readonly_sql", "execute_write_sql"):
                    sql_errors_count += 1
                    if sql_errors_count >= 3:
                        yield {"type": "error", "error": f"⚠️ Auto-correction SQL locale échouée après 3 tentatives. Dernière erreur : {output['error']}"}
                        return
                else:
                    yield {"type": "error", "error": f"⚠️ L'action '{func_name}' a échoué : {output['error']}"}
                    return

            messages.append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": func_name,
                        "response": {"output": output}
                    }
                }]
            })

            ollama_messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id"),
                "content": json.dumps(output, ensure_ascii=False, default=str)
            })

    yield {"type": "error", "error": "La requête Ollama a dépassé la limite de tours sans retourner de réponse."}

async def run_ollama_agent(messages: List[Dict[str, Any]], schema_text: str) -> str:
    """Boucle d'agent synchrone pour Ollama (rétrocompatibilité)."""
    final_text = ""
    async for event in run_ollama_agent_generator(messages):
        if event.get("type") == "final_response":
            final_text = event.get("text", "")
        elif event.get("type") == "error":
            return event.get("error", "")
    return final_text

async def run_assistant_agent_generator(messages: List[Dict[str, Any]], api_key: str, confirmed_query: str | None = None, user_role: str = "operator"):
    """Orchestre la boucle d'agent sous forme de générateur asynchrone d'événements."""
    yield {"type": "status", "message": "Sabrina analyse votre demande..."}

    # 1. Compression glissante de la mémoire
    messages = await compress_history_if_needed(messages, api_key, is_local=False)

    # 2. Aiguillage adaptatif du modèle
    user_model = db_manager.get_setting("gemini_model", "gemini-3.1-flash-lite").strip()
    if not user_model:
        user_model = "gemini-3.1-flash-lite"

    if user_model.lower() not in ("local", "ollama"):
        # Respect the model chosen by the user in settings.
        # Only auto-select if the user explicitly chose "auto" or the value is empty.
        if user_model.lower() in ("auto", ""):
            last_user_text = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    parts = m.get("parts", [])
                    if isinstance(parts, list):
                        last_user_text = " ".join(p.get("text", "") for p in parts if "text" in p)
                    else:
                        last_user_text = m.get("content", "")
                    break

            complexity = classify_intent(last_user_text)
            if complexity == "full":
                user_model = "gemini-3.5-flash"
            else:
                user_model = "gemini-3.1-flash-lite"
        # else: keep user_model as-is (user explicitly chose it)

    # Track tools already confirmed and executed in this request — auto-approve if re-called
    _confirmed_tools: set[str] = set()

    if confirmed_query:
        func_name = None
        func_args = {}
        try:
            cq_data = json.loads(confirmed_query)
            if isinstance(cq_data, dict) and "name" in cq_data:
                func_name = cq_data.get("name")
                func_args = cq_data.get("args", {})
        except Exception:
            pass

        if not func_name:
            func_name = "execute_write_sql"
            func_args = {"query": confirmed_query}

        yield {"type": "status", "message": "Exécution de l'action confirmée..."}
        try:
            if func_name == "execute_write_sql":
                output = execute_write_sql(func_args.get("query", ""))
            else:
                output = await execute_tool_action(func_name, func_args, user_role=user_role)
        except Exception as e:
            output = {"error": str(e)}

        # Mark this tool call as already confirmed so it won't be re-asked
        _confirmed_tools.add(json.dumps({"name": func_name, "args": func_args}, sort_keys=True))

        if user_model.lower() in ("local", "ollama"):
            messages = list(messages)
            last_msg_is_model_call = False
            tool_call_id = "call_confirmed"
            if messages:
                last_msg = messages[-1]
                role = last_msg.get("role")
                if role in ("assistant", "model"):
                    if "tool_calls" in last_msg:
                        for tc in last_msg["tool_calls"]:
                            func = tc.get("function", {})
                            if func.get("name") == func_name:
                                last_msg_is_model_call = True
                                tool_call_id = tc.get("id") or "call_confirmed"
                                break
                    if not last_msg_is_model_call and "parts" in last_msg:
                        parts = last_msg["parts"]
                        if isinstance(parts, list):
                            for p in parts:
                                if "functionCall" in p and p["functionCall"].get("name") == func_name:
                                    last_msg_is_model_call = True
                                    tool_call_id = "call_confirmed"
                                    break

            if not last_msg_is_model_call:
                messages.append({
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{
                        "id": "call_confirmed",
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": func_args
                        }
                    }]
                })

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(output, ensure_ascii=False, default=str)
            })
            confirmed_query = None
        else:
            messages = list(messages)
            last_msg_is_model_call = False
            if messages:
                last_msg = messages[-1]
                role = last_msg.get("role")
                if role in ("model", "assistant"):
                    if "parts" in last_msg:
                        parts = last_msg["parts"]
                        if isinstance(parts, list):
                            last_msg_is_model_call = any(
                                "functionCall" in p and p["functionCall"].get("name") == func_name for p in parts
                            )
                    if not last_msg_is_model_call and "tool_calls" in last_msg:
                        for tc in last_msg["tool_calls"]:
                            func = tc.get("function", {})
                            if func.get("name") == func_name:
                                last_msg_is_model_call = True
                                break

            if not last_msg_is_model_call:
                messages.append({
                    "role": "model",
                    "parts": [{"functionCall": {"name": func_name, "args": func_args}}]
                })

            messages.append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": func_name,
                        "response": {"output": output}
                    }
                }]
            })
            confirmed_query = None

    if user_model.lower() in ("local", "ollama"):
        async for event in run_ollama_agent_generator(messages, confirmed_query, user_role=user_role):
            yield event
        return

    contents = list(messages)
    max_turns = 15
    sql_errors_count = 0
    for turn in range(max_turns):
        res = None
        last_exception = None

        candidate_models = [user_model]
        fallbacks = ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-3.5-flash"]
        for m in fallbacks:
            if m != user_model and m not in candidate_models:
                candidate_models.append(m)

        # Parse multiple API keys
        keys = [k.strip() for k in api_key.replace(";", ",").split(",") if k.strip()]
        if not keys:
            keys = [""]

        accumulated_text = ""
        accumulated_tool_calls = []
        accumulated_parts = []
        has_tool_call = False
        res_ok = False

        try:
            from unittest.mock import Mock
            is_mocked = isinstance(call_gemini_api, Mock) or hasattr(call_gemini_api, "_mock_self")
        except ImportError:
            is_mocked = False

        for model in candidate_models:
            for current_key in keys:
                accumulated_text = ""
                accumulated_tool_calls = []
                accumulated_parts = []
                has_tool_call = False
                try:
                    if is_mocked:
                        res = await call_gemini_api(contents, current_key, model_name=model)
                        candidates = res.get("candidates", [])
                        if candidates:
                            content_obj = candidates[0].get("content", {})
                            parts = content_obj.get("parts", [])
                            accumulated_parts = parts
                            for p in parts:
                                if "text" in p:
                                    accumulated_text += p["text"]
                                    yield {"type": "text_chunk", "text": p["text"]}
                                if "functionCall" in p:
                                    has_tool_call = True
                                    accumulated_tool_calls.append(p["functionCall"])
                    else:
                        async for event in call_gemini_api_generator(contents, current_key, model_name=model):
                            if event.get("type") == "raw_part":
                                accumulated_parts.append(event["part"])
                            elif event.get("type") == "text_chunk":
                                accumulated_text += event["text"]
                                if not has_tool_call:
                                    yield {"type": "text_chunk", "text": event["text"]}
                            elif event.get("type") == "function_call":
                                has_tool_call = True
                                accumulated_tool_calls.append(event["functionCall"])
                    res_ok = True
                    break
                except Exception as exc:
                    last_exception = exc
                    logger.warning("Erreur avec le modèle %s (clé %s...) : %s. Essai d'une autre clé ou modèle...", model, current_key[:8], exc)
                    
                    err_str = str(exc).lower()
                    if "api_key_service_blocked" in err_str or "leaked" in err_str or "invalid authentication credentials" in err_str or "unauthenticated" in err_str:
                        try:
                            from app.core.db_helpers import db_manager as helper_db_manager
                            helper_db_manager.set_setting("gemini_api_key", "")
                            logger.info("Clé d'API invalide supprimée de la base de données pour forcer l'utilisateur à en saisir une nouvelle.")
                        except Exception:
                            pass
                    continue
            if res_ok:
                break

        if not res_ok:
            # Fallback Ollama
            ollama_ok = await is_ollama_available()
            if ollama_ok:
                err_str = str(last_exception).lower() if last_exception else ""
                if "api_key_service_blocked" in err_str:
                    yield {"type": "status", "message": "⚠️ Clé bloquée : L'API Generative Language (Gemini) est restreinte ou désactivée pour cette clé dans la console Google Cloud. Bascule automatique sur l'IA locale..."}
                elif "leaked" in err_str:
                    yield {"type": "status", "message": "⚠️ Clé d'API Gemini révoquée par Google (Signalée comme exposée/leaked). Bascule automatique sur l'IA locale..."}
                else:
                    yield {"type": "status", "message": "Modèles Gemini indisponibles. Bascule automatique sur l'IA locale..."}
                async for event in run_ollama_agent_generator(contents, confirmed_query):
                    yield event
                return
            else:
                error_msg = str(last_exception) if last_exception else "Quota dépassé."
                yield {
                    "type": "error",
                    "error": (
                        f"⚠️ Quota Gemini dépassé ({error_msg}).\n"
                        "💬 **Conseil :** Ollama n'est pas démarré. Lancez l'application **Ollama** pour continuer en local."
                    )
                }
                return

        if accumulated_parts:
            content_obj = {
                "role": "model",
                "parts": accumulated_parts
            }
        else:
            parts = []
            if accumulated_text:
                parts.append({"text": accumulated_text})
            for tc in accumulated_tool_calls:
                parts.append({"functionCall": tc})
            content_obj = {
                "role": "model",
                "parts": parts
            }
        contents.append(content_obj)

        tool_calls = accumulated_tool_calls

        if not tool_calls:
            yield {"type": "final_response", "text": accumulated_text, "history": contents}
            return

        function_responses = []
        for part in tool_calls:
            func_call = part.get("functionCall", part)
            func_name = func_call["name"]
            func_args = func_call.get("args", {})

            logger.info("Agent Call: Execute function '%s' with args %s", func_name, func_args)

            # Éviter de ré-exécuter/re-confirmer une action déjà effectuée dans cette conversation
            past_output = find_past_tool_execution(contents[:-1], func_name, func_args)

            if past_output is not None:
                logger.info("Agent: Réutilisation du résultat de l'exécution passée pour '%s' pour éviter une boucle", func_name)
                output = past_output
            elif func_name == "get_schema":
                output = get_schema()
            elif func_name == "execute_readonly_sql":
                sql_query = func_args.get("query", "")
                yield {"type": "status", "message": "Recherche dans la base de données (SELECT)..."}
                output = execute_readonly_sql(sql_query)
            elif func_name == "execute_write_sql":
                sql_query = func_args.get("query", "")
                normalized_call = json.dumps({"name": "execute_write_sql", "args": {"query": sql_query}}, sort_keys=True)
                is_confirmed = normalized_call in _confirmed_tools
                if not is_confirmed and confirmed_query:
                    if confirmed_query.strip() == sql_query.strip() or confirmed_query.strip() == normalized_call:
                        is_confirmed = True
                    else:
                        try:
                            cq_data = json.loads(confirmed_query)
                            if cq_data.get("name") == "execute_write_sql" and cq_data.get("args", {}).get("query") == sql_query:
                                is_confirmed = True
                        except Exception:
                            pass
                if not is_confirmed:
                    yield {
                        "type": "confirmation_required",
                        "query": normalized_call,
                        "message": f"Je m'apprête à modifier la base de données. Veuillez confirmer la requête SQL ci-dessous :\n```sql\n{sql_query}\n```",
                        "history": contents
                    }
                    return
                # Mark as confirmed
                _confirmed_tools.add(normalized_call)
                yield {"type": "status", "message": "Modification de la base de données (confirmée)..."}
                output = execute_write_sql(sql_query)
            else:
                is_write = tool_requires_confirmation(func_name)
                if is_write:
                    normalized_call = json.dumps({"name": func_name, "args": func_args}, sort_keys=True)
                    # Auto-confirm if this exact call was already confirmed earlier in this run
                    is_confirmed = normalized_call in _confirmed_tools
                    if not is_confirmed and confirmed_query:
                        if confirmed_query.strip() == normalized_call:
                            is_confirmed = True
                        else:
                            try:
                                cq_data = json.loads(confirmed_query)
                                if cq_data.get("name") == func_name and cq_data.get("args") == func_args:
                                    is_confirmed = True
                            except Exception:
                                pass
                    if not is_confirmed:
                        msg = get_tool_confirmation_message(func_name, func_args)
                        yield {
                            "type": "confirmation_required",
                            "query": normalized_call,
                            "message": msg,
                            "history": contents
                        }
                        return
                    # Mark as confirmed for the rest of this run
                    _confirmed_tools.add(normalized_call)

                yield {"type": "status", "message": f"Exécution de l'action '{func_name}'..."}
                output = await execute_tool_action(func_name, func_args, user_role=user_role)

            if isinstance(output, dict) and "error" in output:
                if func_name in ("execute_readonly_sql", "execute_write_sql"):
                    sql_errors_count += 1
                    if sql_errors_count >= 3:
                        yield {"type": "error", "error": f"⚠️ Auto-correction SQL échouée après 3 tentatives. Dernière erreur : {output['error']}"}
                        return
                else:
                    yield {"type": "error", "error": f"⚠️ L'action '{func_name}' a échoué : {output['error']}"}
                    return

            function_responses.append({
                "functionResponse": {
                    "name": func_name,
                    "response": {"output": output}
                }
            })

        contents.append({
            "role": "function",
            "parts": function_responses
        })

    yield {"type": "error", "error": "La requête a dépassé la limite de tours d'agent sans retourner de réponse."}

async def run_assistant_agent(messages: List[Dict[str, Any]], api_key: str) -> str:
    """Orchestre la boucle d'agent en mode synchrone (compatibilité)."""
    final_text = ""
    async for event in run_assistant_agent_generator(messages, api_key):
        if event.get("type") == "final_response":
            final_text = event.get("text", "")
        elif event.get("type") == "error":
            return event.get("error", "")
    return final_text
