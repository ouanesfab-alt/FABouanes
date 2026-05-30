import pytest
import os
import time
import asyncio
from unittest.mock import patch, MagicMock

from app.core.security import (
    encrypt_val,
    decrypt_val,
    get_client_key_sync,
    create_client_key_sync,
    delete_client_key_sync
)
from app.core.db_access import execute_db, query_db
from app.repositories.client_repository import (
    insert_client,
    get_client,
    update_client,
    list_clients,
    shred_client
)
from app.core.worker import dispatch_outbox_events_task, replay_dead_letter_events_task
from app.repositories.dashboard_repository import refresh_client_balances_view

def test_cryptography_helpers():
    key = b"01234567890123456789012345678912"  # 32 bytes
    plaintext = "Hello World"
    
    # Encrypt
    ciphertext = encrypt_val(plaintext, key)
    assert ciphertext is not None
    assert ciphertext.startswith("ale:")
    
    # Decrypt with correct key
    decrypted = decrypt_val(ciphertext, key)
    assert decrypted == plaintext
    
    # Decrypt legacy plaintext (must return it as-is)
    assert decrypt_val("Normal address", key) == "Normal address"
    assert decrypt_val("", key) == ""
    assert decrypt_val(None, key) is None
    
    # Decrypt with missing key (must return shredded marker)
    assert decrypt_val(ciphertext, None) == "[DONNÉES SUPPRIMÉES]"
    
    # Decrypt with wrong key (must return shredded marker)
    wrong_key = b"wrongkeywrongkeywrongkeywrongkey"
    assert decrypt_val(ciphertext, wrong_key) == "[DONNÉES SUPPRIMÉES]"


def test_key_database_storage():
    # Setup dummy client
    client_id = 99999
    delete_client_key_sync(client_id)
    
    # Create key
    key = create_client_key_sync(client_id)
    assert key is not None
    assert len(key) == 32
    
    # Retrieve key
    retrieved = get_client_key_sync(client_id)
    assert retrieved == key
    
    # Delete/shred key
    delete_client_key_sync(client_id)
    assert get_client_key_sync(client_id) is None


def test_client_ale_integration():
    # Insert new client
    client_name = "ALE Test Client"
    phone = "0612345678"
    address = "123 Cryptography Lane"
    notes = "Test notes"
    opening_credit = 150.0
    
    client_id = insert_client(client_name, phone, address, notes, opening_credit)
    assert client_id > 0
    
    # Retrieve raw values in database directly via SQL to verify they are encrypted
    rows = query_db("SELECT phone, address FROM clients WHERE id = %s", (client_id,))
    assert len(rows) == 1
    raw_phone = rows[0]["phone"]
    raw_address = rows[0]["address"]
    
    assert raw_phone.startswith("ale:")
    assert raw_address.startswith("ale:")
    assert raw_phone != phone
    assert raw_address != address
    
    # Retrieve via repository to verify auto-decryption
    client = get_client(client_id)
    assert client is not None
    assert client["phone"] == phone
    assert client["address"] == address
    
    # Update client PII
    new_phone = "0799999999"
    new_address = "456 Decrypted Blvd"
    update_client(client_id, client_name, new_phone, new_address, notes, opening_credit)
    
    # Verify raw values are still encrypted in database
    rows_upd = query_db("SELECT phone, address FROM clients WHERE id = %s", (client_id,))
    assert rows_upd[0]["phone"].startswith("ale:")
    assert rows_upd[0]["phone"] != new_phone
    
    # Verify repository decypts new values
    client_upd = get_client(client_id)
    assert client_upd["phone"] == new_phone
    assert client_upd["address"] == new_address
    
    # Test Shredding PII
    shred_client(client_id)
    
    # Check that key is deleted
    assert get_client_key_sync(client_id) is None
    
    # Check stored values are shred markers
    rows_shred = query_db("SELECT phone, address FROM clients WHERE id = %s", (client_id,))
    assert rows_shred[0]["phone"] == "[SHREDDED]"
    assert rows_shred[0]["address"] == "[SHREDDED]"
    
    # Check repository decrypt returns the shredded message
    client_shred = get_client(client_id)
    assert client_shred["phone"] == "[SHREDDED]"
    assert client_shred["address"] == "[SHREDDED]"


def test_outbox_dlq_redirection():
    # Clean DLQ and Outbox
    execute_db("DELETE FROM outbox_events")
    execute_db("DELETE FROM dead_letter_events")
    
    # Insert a failing event (e.g. invalid deserialized content or trigger failure)
    # We will insert a payload that triggers a handler failure or deserialization failure.
    # E.g. raw JSON that cannot be parsed by deserialize
    execute_db(
        "INSERT INTO outbox_events (event_type, payload, retry_count) VALUES (%s, %s, %s)",
        ("invalid.event", "malformed_json_payload", 0)
    )
    
    # Run dispatcher 4 times -> retry_count should increment
    for expected_retry in range(1, 5):
        processed = asyncio.run(dispatch_outbox_events_task({}))
        assert processed == 0  # not processed successfully
        
        rows = query_db("SELECT retry_count, last_error FROM outbox_events")
        assert len(rows) == 1
        assert rows[0]["retry_count"] == expected_retry
        assert "Deserialization failed" in rows[0]["last_error"]
        
    # On the 5th attempt, it should be deleted from outbox and moved to dead_letter_events
    processed = asyncio.run(dispatch_outbox_events_task({}))
    assert processed == 0
    
    # Outbox should be empty
    rows_outbox = query_db("SELECT id FROM outbox_events")
    assert len(rows_outbox) == 0
    
    # DLQ should contain the event
    rows_dlq = query_db("SELECT event_type, payload, reason FROM dead_letter_events")
    assert len(rows_dlq) == 1
    assert rows_dlq[0]["event_type"] == "invalid.event"
    assert rows_dlq[0]["payload"] == "malformed_json_payload"
    assert "Deserialization failed" in rows_dlq[0]["reason"]


def test_dlq_replay():
    # Clean DLQ and Outbox
    execute_db("DELETE FROM outbox_events")
    execute_db("DELETE FROM dead_letter_events")
    
    # Insert event to DLQ
    execute_db(
        "INSERT INTO dead_letter_events (event_type, payload, reason) VALUES (%s, %s, %s)",
        ("replay.event", "test_payload", "some error")
    )
    
    # Run replay task
    replayed = asyncio.run(replay_dead_letter_events_task({}))
    assert replayed == 1
    
    # DLQ should be empty
    rows_dlq = query_db("SELECT id FROM dead_letter_events")
    assert len(rows_dlq) == 0
    
    # Outbox should contain the event with reset retry_count and last_error
    rows_outbox = query_db("SELECT event_type, payload, retry_count, last_error FROM outbox_events")
    assert len(rows_outbox) == 1
    assert rows_outbox[0]["event_type"] == "replay.event"
    assert rows_outbox[0]["payload"] == "test_payload"
    assert rows_outbox[0]["retry_count"] == 0
    assert rows_outbox[0]["last_error"] is None


def test_dashboard_refresh_debounce():
    # Mock Redis to simulate lock
    mock_redis = MagicMock()
    
    # First call: lock is acquired (returns True)
    # Second call: lock is NOT acquired (returns None)
    mock_redis.set.side_effect = [True, None, None]
    
    with patch("redis.from_url", return_value=mock_redis), \
         patch("app.repositories.dashboard_repository.execute_db") as mock_execute:
         
         # Call 1
         refresh_client_balances_view()
         # Call 2 (should be debounced)
         refresh_client_balances_view()
         # Call 3 (should be debounced)
         refresh_client_balances_view()
         
         # execute_db should only be called once!
         mock_execute.assert_called_once()
         assert mock_execute.call_count == 1
