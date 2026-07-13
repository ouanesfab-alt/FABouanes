# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from app.modules.assistant.confirmations import (
    tool_requires_confirmation,
    get_tool_confirmation_message,
    READ_ONLY_TOOL_NAMES
)
from app.modules.assistant.memory import (
    remember,
    recall,
    forget,
    get_context_memories
)


# =============================================================================
# 1. Tests confirmations.py
# =============================================================================

def test_tool_requires_confirmation():
    # Read-only tools should not require confirmation
    for tool in READ_ONLY_TOOL_NAMES:
        assert tool_requires_confirmation(tool) is False

    # Write operations must require confirmation
    assert tool_requires_confirmation("execute_write_sql") is True
    assert tool_requires_confirmation("add_client") is True
    assert tool_requires_confirmation("delete_operation") is True


@patch("app.modules.assistant.confirmations.dry_run_sql")
def test_get_tool_confirmation_messages(mock_dry_run):
    mock_dry_run.return_value = "Simulation dry-run OK"

    # execute_write_sql
    msg = get_tool_confirmation_message("execute_write_sql", {"query": "UPDATE clients SET name = 'X'"})
    assert "UPDATE clients" in msg
    assert "Simulation dry-run OK" in msg

    # modify_app_file
    msg = get_tool_confirmation_message("modify_app_file", {
        "filepath": "app/main.py", "old_content": "A", "new_content": "B"
    })
    assert "app/main.py" in msg
    assert "Avant :" in msg
    assert "Après :" in msg

    # restore_app_backup
    msg = get_tool_confirmation_message("restore_app_backup", {"backup_name": "backup.sql"})
    assert "backup.sql" in msg

    # create_app_user
    msg = get_tool_confirmation_message("create_app_user", {"username": "jean", "role": "admin"})
    assert "jean" in msg
    assert "admin" in msg

    # change_app_user_password
    msg = get_tool_confirmation_message("change_app_user_password", {"username": "jean"})
    assert "jean" in msg

    # delete_app_user
    msg = get_tool_confirmation_message("delete_app_user", {"username": "jean"})
    assert "jean" in msg

    # update_setting
    msg = get_tool_confirmation_message("update_setting", {"key": "k", "value": "v"})
    assert "k" in msg
    assert "v" in msg

    # add_client
    msg = get_tool_confirmation_message("add_client", {"name": "Lamine", "phone": "0555", "opening_credit": 1500})
    assert "Lamine" in msg
    assert "0555" in msg
    assert "1500" in msg

    # modify_client
    msg = get_tool_confirmation_message("modify_client", {"client_id": 42})
    assert "42" in msg

    # delete_client
    msg = get_tool_confirmation_message("delete_client", {"client_id": 42})
    assert "42" in msg

    # add_supplier
    msg = get_tool_confirmation_message("add_supplier", {"name": "Somacob"})
    assert "Somacob" in msg

    # modify_supplier
    msg = get_tool_confirmation_message("modify_supplier", {"supplier_id": 12})
    assert "12" in msg

    # delete_supplier
    msg = get_tool_confirmation_message("delete_supplier", {"supplier_id": 12})
    assert "12" in msg

    # add_sale
    msg = get_tool_confirmation_message("add_sale", {"quantity": 10, "unit": "sac", "unit_price": 2500, "amount_paid": 5000})
    assert "10" in msg
    assert "sac" in msg
    assert "2500" in msg
    assert "5000" in msg

    # add_purchase
    msg = get_tool_confirmation_message("add_purchase", {"quantity": 5, "unit": "Tonne", "unit_price": 85000})
    assert "5" in msg
    assert "85000" in msg

    # add_payment
    msg = get_tool_confirmation_message("add_payment", {"amount": 35000, "client_id": 19})
    assert "35000" in msg
    assert "19" in msg

    # add_supplier_payment
    msg = get_tool_confirmation_message("add_supplier_payment", {"amount": 12000, "supplier_id": 4, "payment_type": "avance"})
    assert "12000" in msg
    assert "4" in msg
    assert "avance" in msg

    # delete_operation
    msg = get_tool_confirmation_message("delete_operation", {"tx_kind": "vente", "tx_id": 101})
    assert "vente" in msg
    assert "101" in msg

    # add_expense
    msg = get_tool_confirmation_message("add_expense", {"amount": 450, "category": "transport"})
    assert "450" in msg
    assert "transport" in msg

    # modify_expense
    msg = get_tool_confirmation_message("modify_expense", {"expense_id": 3})
    assert "3" in msg

    # delete_expense
    msg = get_tool_confirmation_message("delete_expense", {"expense_id": 3})
    assert "3" in msg

    # add_production_batch
    msg = get_tool_confirmation_message("add_production_batch", {"finished_product_id": 8, "quantity": 120})
    assert "8" in msg
    assert "120" in msg

    # delete_production
    msg = get_tool_confirmation_message("delete_production", {"batch_id": 77})
    assert "77" in msg

    # create_user_note
    msg = get_tool_confirmation_message("create_user_note", {"title": "Note Test"})
    assert "Note Test" in msg

    # save_user_note
    msg = get_tool_confirmation_message("save_user_note", {"title": "Note Modifiée", "note_id": 4})
    assert "Note Modifiée" in msg

    # delete_user_note
    msg = get_tool_confirmation_message("delete_user_note", {"note_id": 4})
    assert "4" in msg

    # add_product
    msg = get_tool_confirmation_message("add_product", {"name": "Produit X", "category": "produit", "price": 1200, "stock_qty": 50})
    assert "Produit X" in msg
    assert "1200" in msg
    assert "50" in msg

    # modify_product
    msg = get_tool_confirmation_message("modify_product", {"product_id": 9, "category": "matiere_premiere"})
    assert "9" in msg

    # delete_product
    msg = get_tool_confirmation_message("delete_product", {"product_id": 9, "category": "matiere_premiere"})
    assert "9" in msg

    # create_recipe
    msg = get_tool_confirmation_message("create_recipe", {"name": "Recette X", "finished_product_id": 1, "items": [{"id": 1}]})
    assert "Recette X" in msg
    assert "1" in msg

    # delete_recipe
    msg = get_tool_confirmation_message("delete_recipe", {"recipe_id": 15})
    assert "15" in msg

    # import_bulk_clients_excel
    msg = get_tool_confirmation_message("import_bulk_clients_excel", {"filepath": "clients.xlsx"})
    assert "clients.xlsx" in msg

    # import_bulk_products_excel
    msg = get_tool_confirmation_message("import_bulk_products_excel", {"filepath": "produits.xlsx", "is_raw_material": True})
    assert "produits.xlsx" in msg
    assert "matières premières" in msg

    # import_client_excel
    msg = get_tool_confirmation_message("import_client_excel", {"filepath": "client_mono.xlsx"})
    assert "client_mono.xlsx" in msg

    # import_client_history_excel
    msg = get_tool_confirmation_message("import_client_history_excel", {"client_id": 10, "filepath": "history.xlsx"})
    assert "10" in msg
    assert "history.xlsx" in msg

    # save_backup_settings
    msg = get_tool_confirmation_message("save_backup_settings", {"gdrive_backup_dir": "c:/backups"})
    assert "c:/backups" in msg

    # update_app_user
    msg = get_tool_confirmation_message("update_app_user", {"user_id": 3, "role": "manager"})
    assert "3" in msg
    assert "manager" in msg

    # forget
    msg = get_tool_confirmation_message("forget", {"memory_id": 204})
    assert "204" in msg

    # Fallback default message
    msg = get_tool_confirmation_message("unknown_action_xyz", {"param": "val"})
    assert "unknown_action_xyz" in msg
    assert "val" in msg


# =============================================================================
# 2. Tests memory.py
# =============================================================================

@patch("app.core.db_helpers.db_manager.execute_db")
@patch("app.core.db_helpers.db_manager.query_db")
def test_remember_success(mock_query, mock_execute):
    # Mocking: No duplicates found, insert returns id 10
    mock_query.return_value = []
    mock_execute.return_value = 10
    res = remember("Toujours arrondir les montants en DA.", category="learned", source="user_explicit")
    assert res.get("success") is True
    assert res.get("memory_id") == 10
    assert "catégorie: learned" in res.get("message")


def test_remember_empty():
    res = remember("   ")
    assert "error" in res
    assert "vide" in res["error"]


@patch("app.core.db_helpers.db_manager.query_db")
def test_remember_duplicate(mock_query):
    # Mocking: Duplicate search returns an existing id 42
    mock_query.return_value = [[42]]
    res = remember("La clé d'API Google est secrète.")
    assert res.get("status") == "already_known"
    assert "mémoire #42" in res.get("message")


@patch("app.core.db_helpers.db_manager.query_db")
def test_remember_exception(mock_query):
    mock_query.side_effect = Exception("DB Connection timeout")
    res = remember("Des souvenirs perdus...")
    assert "error" in res
    assert "DB Connection timeout" in res["error"]


@patch("app.core.db_helpers.db_manager.query_db")
def test_recall_empty_query(mock_query):
    mock_query.return_value = [
        {"id": 1, "category": "preference", "content": "Préfère Outfit", "source": "user", "relevance_score": 1, "created_at": "2026-07-01"}
    ]
    res = recall("", limit=5)
    assert res.get("count") == 1
    assert len(res.get("memories")) == 1
    assert res.get("memories")[0]["content"] == "Préfère Outfit"


@patch("app.core.db_helpers.db_manager.query_db")
def test_recall_with_query(mock_query):
    mock_query.return_value = [
        {"id": 2, "category": "rule", "content": "TVA à 19%", "source": "system", "relevance_score": 2, "created_at": "2026-07-02"}
    ]
    res = recall("tva")
    assert res.get("count") == 1
    assert res.get("memories")[0]["content"] == "TVA à 19%"


@patch("app.core.db_helpers.db_manager.query_db")
def test_recall_tuples_resilience(mock_query):
    # Simulates DB returning list of raw tuples instead of dictionaries
    mock_query.return_value = [
        (3, "learned", "Arrondir à 2 décimales", "user", 0, "2026-07-03")
    ]
    res = recall("décimales")
    assert res.get("count") == 1
    mem = res.get("memories")[0]
    assert mem["id"] == 3
    assert mem["category"] == "learned"
    assert mem["content"] == "Arrondir à 2 décimales"


@patch("app.core.db_helpers.db_manager.query_db")
def test_recall_exception(mock_query):
    mock_query.side_effect = Exception("FTS index corrupt")
    res = recall("something")
    assert "error" in res
    assert "FTS index corrupt" in res["error"]


@patch("app.core.db_helpers.db_manager.execute_db")
def test_forget_success(mock_execute):
    mock_execute.return_value = 50
    res = forget(50)
    assert res.get("success") is True
    assert "supprimé" in res.get("message")


@patch("app.core.db_helpers.db_manager.execute_db")
def test_forget_not_found(mock_execute):
    mock_execute.return_value = 0
    res = forget(999)
    assert "error" in res
    assert "introuvable" in res["error"]


@patch("app.core.db_helpers.db_manager.execute_db")
def test_forget_exception(mock_execute):
    mock_execute.side_effect = Exception("Lock wait timeout")
    res = forget(12)
    assert "error" in res
    assert "Lock wait timeout" in res["error"]


@patch("app.core.db_helpers.db_manager.query_db")
def test_get_context_memories_formatted(mock_query):
    # Mocking database to return memories across different categories
    mock_query.return_value = [
        {"category": "preference", "content": "Ranger par date"},
        {"category": "rule", "content": "Toujours exiger acompte"},
        {"category": "correction", "content": "Pas de TVA sur aliments"},
        {"category": "learned", "content": "Somacob fournisseur principal"},
        {"category": "unknown_cat", "content": "Souvenir divers"}
    ]
    ctx = get_context_memories()
    assert "MÉMOIRE PERSISTANTE DE SABRINA" in ctx
    assert "⭐ [preference] Ranger par date" in ctx
    assert "📌 [rule] Toujours exiger acompte" in ctx
    assert "⚠️ [correction] Pas de TVA sur aliments" in ctx
    assert "🧠 [learned] Somacob fournisseur principal" in ctx
    assert "💡 [unknown_cat] Souvenir divers" in ctx


@patch("app.core.db_helpers.db_manager.query_db")
def test_get_context_memories_empty(mock_query):
    mock_query.return_value = []
    ctx = get_context_memories()
    assert ctx == ""


@patch("app.core.db_helpers.db_manager.query_db")
def test_get_context_memories_exception(mock_query):
    mock_query.side_effect = Exception("DB Offline")
    ctx = get_context_memories()
    # Should handle exceptions gracefully and return an empty string
    assert ctx == ""


def test_find_past_tool_execution():
    from app.modules.assistant.service import find_past_tool_execution

    # Test case 1: Gemini format, matching call and response
    messages_gemini = [
        {"role": "user", "parts": [{"text": "ajoute client Jean"}]},
        {
            "role": "model",
            "parts": [
                {"text": "Je vais ajouter le client Jean."},
                {"functionCall": {"name": "add_client", "args": {"name": "Jean", "phone": "0555"}}}
            ]
        },
        {
            "role": "function",
            "parts": [
                {
                    "functionResponse": {
                        "name": "add_client",
                        "response": {"output": {"id": 123, "status": "success"}}
                    }
                }
            ]
        }
    ]

    # Matching call (exact same args)
    res = find_past_tool_execution(messages_gemini, "add_client", {"name": "Jean", "phone": "0555"})
    assert res == {"id": 123, "status": "success"}

    # Matching call (minor arg differences like type or None)
    res = find_past_tool_execution(messages_gemini, "add_client", {"name": "Jean", "phone": "0555", "notes": None})
    assert res == {"id": 123, "status": "success"}

    # Mismatched call (different args)
    res = find_past_tool_execution(messages_gemini, "add_client", {"name": "Jean", "phone": "0666"})
    assert res is None

    # Test case 2: OpenAI / Ollama format
    messages_openai = [
        {"role": "user", "content": "Ajoute un versement"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "add_payment",
                        "arguments": {"amount": 100.0, "client_id": 42}
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": '{"output": {"status": "success", "payment_id": 5}}'
        }
    ]

    # Matching call
    res = find_past_tool_execution(messages_openai, "add_payment", {"amount": 100, "client_id": 42})
    assert res == {"status": "success", "payment_id": 5}

