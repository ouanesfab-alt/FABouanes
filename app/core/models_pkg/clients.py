"""Modèles SQLModel pour le module Clients."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class Client(SQLModel, table=True):
    __tablename__ = "clients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    opening_credit: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ImportedClientHistory(SQLModel, table=True):
    __tablename__ = "imported_client_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    source_file: Optional[str] = Field(default=None)
    entry_date: date  # Migré TEXT→DATE (migration 0035)
    designation: Optional[str] = Field(default=None)
    debit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    credit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    running_balance: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    imported_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)


class ClientHistory(SQLModel, table=True):
    __tablename__ = "client_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    operation_date: date
    designation: str = Field(default="")
    montant_achat: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    montant_verse: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    solde_cumule: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    ordre_import: int = Field(default=0)
    source: str = Field(default="import_excel")
    sale_id: Optional[int] = Field(default=None)
    raw_sale_id: Optional[int] = Field(default=None)
    payment_id: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)


class ClientKey(SQLModel, table=True):
    __tablename__ = "client_keys"

    client_id: int = Field(primary_key=True)
    encryption_key: str
