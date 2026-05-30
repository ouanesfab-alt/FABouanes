from __future__ import annotations

import functools
import asyncio
from typing import Optional, List, Tuple
from decimal import Decimal
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker

def async_compat(func):
    """Allows an async function to be called synchronously if no event loop is running."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not None and loop.is_running():
            return func(*args, **kwargs)
        else:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(func(*args, **kwargs))
    return wrapper

from app.core.security import encrypt_val, decrypt_val

async def _get_client_key(client_id: int, session: AsyncSession) -> Optional[bytes]:
    import base64
    stmt = text("SELECT encryption_key FROM client_keys WHERE client_id = :client_id")
    res = await session.execute(stmt, {"client_id": client_id})
    row = res.mappings().first()
    if row and row["encryption_key"]:
        return base64.b64decode(row["encryption_key"])
    return None

async def _create_client_key(client_id: int, session: AsyncSession) -> bytes:
    import os
    import base64
    key = os.urandom(32)
    b64_key = base64.b64encode(key).decode("utf-8")
    stmt = text(
        "INSERT INTO client_keys (client_id, encryption_key) VALUES (:client_id, :key) "
        "ON CONFLICT (client_id) DO UPDATE SET encryption_key = EXCLUDED.encryption_key"
    )
    await session.execute(stmt, {"client_id": client_id, "key": b64_key})
    return key

async def _decrypt_client_dict(client_dict: dict, session: AsyncSession) -> dict:
    if not client_dict:
        return client_dict
    client_id = client_dict.get("id")
    if not client_id:
        return client_dict
    key = await _get_client_key(client_id, session)
    decrypted = dict(client_dict)
    decrypted["phone"] = decrypt_val(client_dict.get("phone"), key)
    decrypted["address"] = decrypt_val(client_dict.get("address"), key)
    return decrypted

async def _decrypt_client_dicts(client_dicts: list[dict], session: AsyncSession) -> list[dict]:
    if not client_dicts:
        return client_dicts
    client_ids = [c["id"] for c in client_dicts if c.get("id")]
    if not client_ids:
        return client_dicts
    from sqlalchemy import bindparam
    stmt = text("SELECT client_id, encryption_key FROM client_keys WHERE client_id IN :ids").bindparams(
        bindparam("ids", expanding=True)
    )
    import base64
    res = await session.execute(stmt, {"ids": tuple(client_ids)})
    keys_map = {}
    for row in res.mappings().all():
        keys_map[row["client_id"]] = base64.b64decode(row["encryption_key"])
    decrypted_list = []
    for client in client_dicts:
        cid = client.get("id")
        key = keys_map.get(cid) if cid else None
        decrypted = dict(client)
        decrypted["phone"] = decrypt_val(client.get("phone"), key)
        decrypted["address"] = decrypt_val(client.get("address"), key)
        decrypted_list.append(decrypted)
    return decrypted_list

@async_compat
async def shred_client(
    client_id: int,
    session: Optional[AsyncSession] = None,
) -> None:
    """Shreds client sensitive PII by deleting their key and setting values to [SHREDDED]."""
    if session is None:
        async with get_async_sessionmaker()() as sess:
            await _shred_client_impl(client_id, sess)
            await sess.commit()
    else:
        await _shred_client_impl(client_id, session)

async def _shred_client_impl(client_id: int, session: AsyncSession) -> None:
    stmt_del = text("DELETE FROM client_keys WHERE client_id = :client_id")
    await session.execute(stmt_del, {"client_id": client_id})
    stmt_upd = text("UPDATE clients SET phone = '[SHREDDED]', address = '[SHREDDED]' WHERE id = :client_id")
    await session.execute(stmt_upd, {"client_id": client_id})

@async_compat
async def insert_client(
    name: str,
    phone: str,
    address: str,
    notes: str,
    opening_credit: float,
    session: Optional[AsyncSession] = None,
) -> int:
    """Inserts a new client using the async session and returns their ID."""
    if session is None:
        async with get_async_sessionmaker()() as sess:
            val = await _insert_client_impl(name, phone, address, notes, opening_credit, sess)
            await sess.commit()
            return val
    else:
        return await _insert_client_impl(name, phone, address, notes, opening_credit, session)

async def _insert_client_impl(
    name: str,
    phone: str,
    address: str,
    notes: str,
    opening_credit: float,
    session: AsyncSession,
) -> int:
    stmt = text(
        "INSERT INTO clients (name, phone, address, notes, opening_credit, created_at, updated_at) "
        "VALUES (:name, '', '', :notes, :opening_credit, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
        "RETURNING id"
    )
    params = {
        "name": name,
        "notes": notes,
        "opening_credit": Decimal(str(opening_credit)),
    }
    res = await session.execute(stmt, params)
    client_id = res.scalar_one()
    
    key = await _create_client_key(client_id, session)
    enc_phone = encrypt_val(phone, key)
    enc_address = encrypt_val(address, key)
    
    upd = text("UPDATE clients SET phone = :phone, address = :address WHERE id = :id")
    await session.execute(upd, {"id": client_id, "phone": enc_phone, "address": enc_address})
    return client_id

@async_compat
async def get_client(
    client_id: int,
    session: Optional[AsyncSession] = None,
) -> Optional[dict]:
    """Retrieves a client by ID as a dictionary for compatibility."""
    stmt = text("SELECT * FROM clients WHERE id = :id")
    if session is None:
        async with get_async_sessionmaker()() as sess:
            res = await sess.execute(stmt, {"id": client_id})
            row = res.mappings().first()
            if not row:
                return None
            return await _decrypt_client_dict(dict(row), sess)
    else:
        res = await session.execute(stmt, {"id": client_id})
        row = res.mappings().first()
        if not row:
            return None
        return await _decrypt_client_dict(dict(row), session)

@async_compat
async def update_client(
    client_id: int,
    name: str,
    phone: str,
    address: str,
    notes: str,
    opening_credit: float,
    session: Optional[AsyncSession] = None,
) -> None:
    """Updates a client's information asynchronously."""
    if session is None:
        async with get_async_sessionmaker()() as sess:
            await _update_client_impl(client_id, name, phone, address, notes, opening_credit, sess)
            await sess.commit()
    else:
        await _update_client_impl(client_id, name, phone, address, notes, opening_credit, session)

async def _update_client_impl(
    client_id: int,
    name: str,
    phone: str,
    address: str,
    notes: str,
    opening_credit: float,
    session: AsyncSession,
) -> None:
    key = await _get_client_key(client_id, session)
    if not key:
        key = await _create_client_key(client_id, session)
    enc_phone = encrypt_val(phone, key)
    enc_address = encrypt_val(address, key)
    stmt = text(
        "UPDATE clients SET name = :name, phone = :phone, address = :address, "
        "notes = :notes, opening_credit = :opening_credit, updated_at = CURRENT_TIMESTAMP "
        "WHERE id = :id"
    )
    params = {
        "id": client_id,
        "name": name,
        "phone": enc_phone,
        "address": enc_address,
        "notes": notes,
        "opening_credit": Decimal(str(opening_credit)),
    }
    await session.execute(stmt, params)

@async_compat
async def find_client_by_name(
    name: str,
    session: Optional[AsyncSession] = None,
) -> Optional[dict]:
    """Finds a client by case-insensitive name matching."""
    stmt = text("SELECT id, name FROM clients WHERE lower(trim(name)) = lower(trim(:name))")
    if session is None:
        async with get_async_sessionmaker()() as sess:
            res = await sess.execute(stmt, {"name": name})
            row = res.mappings().first()
            return dict(row) if row else None
    else:
        res = await session.execute(stmt, {"name": name})
        row = res.mappings().first()
        return dict(row) if row else None

@async_compat
async def list_clients(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    session: Optional[AsyncSession] = None,
) -> Tuple[List[dict], int]:
    """Lists clients asynchronously with pagination and french text search."""
    where: List[str] = []
    params: dict = {}
    
    if search:
        where.append("search_vector @@ plainto_tsquery('french', :search)")
        params["search"] = search
        
    base_query = "SELECT * FROM clients_with_stats"
    if where:
        base_query += " WHERE " + " AND ".join(where)
    
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset
    
    wrapped = f"SELECT *, COUNT(*) OVER() AS _total_count FROM ({base_query}) _q ORDER BY name LIMIT :limit OFFSET :offset"
    
    if session is None:
        async with get_async_sessionmaker()() as sess:
            res = await sess.execute(text(wrapped), params)
            rows = [dict(r) for r in res.mappings().all()]
            rows = await _decrypt_client_dicts(rows, sess)
    else:
        res = await session.execute(text(wrapped), params)
        rows = [dict(r) for r in res.mappings().all()]
        rows = await _decrypt_client_dicts(rows, session)
        
    total = int(rows[0]["_total_count"]) if rows else 0
    return rows, total

@async_compat
async def list_clients_with_balance(
    search: str | None = None,
    page: int = 1,
    page_size: int = 50,
    session: Optional[AsyncSession] = None,
) -> Tuple[List[dict], int]:
    """List clients with balance using pagination and french search."""
    return await list_clients(search, page, page_size, session)



