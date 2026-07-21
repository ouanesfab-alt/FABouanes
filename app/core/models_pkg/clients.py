"""Modèles SQLModel pour le module Clients."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING
from sqlalchemy import Column, Numeric
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy.orm import relationship
from pydantic import field_validator

if TYPE_CHECKING:
    from app.core.models_pkg.payments import Payment
    from app.core.models_pkg.sales import Sale, RawSale, SaleDocument


from app.core.model_utils import _now


class Client(SQLModel, table=True):
    __tablename__ = "clients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    opening_credit: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    # Relationships
    imported_histories: list["ImportedClientHistory"] = Relationship(sa_relationship=relationship("ImportedClientHistory", back_populates="client"))
    histories: list["ClientHistory"] = Relationship(sa_relationship=relationship("ClientHistory", back_populates="client"))
    sales: list["Sale"] = Relationship(sa_relationship=relationship("Sale", back_populates="client"))
    raw_sales: list["RawSale"] = Relationship(sa_relationship=relationship("RawSale", back_populates="client"))
    payments: list["Payment"] = Relationship(sa_relationship=relationship("Payment", back_populates="client"))
    sale_documents: list["SaleDocument"] = Relationship(sa_relationship=relationship("SaleDocument", back_populates="client"))


    @field_validator("opening_credit", mode="before")
    @classmethod
    def _coerce_opening_credit(cls, v: Any) -> Decimal:
        """Coerce float/str retournés par SQLite en Decimal."""
        if not isinstance(v, Decimal):
            return Decimal(str(v))
        return v


class ImportedClientHistory(SQLModel, table=True):
    __tablename__ = "imported_client_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    source_file: Optional[str] = Field(default=None)

    # Relationships
    client: Client = Relationship(sa_relationship=relationship("Client", back_populates="imported_histories"))
    entry_date: date  # Migré TEXT→DATE (migration 0035)
    designation: Optional[str] = Field(default=None)
    debit_amount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    credit_amount: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    running_balance: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    imported_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=_now)


class ClientHistory(SQLModel, table=True):
    __tablename__ = "client_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    operation_date: date

    # Relationships
    client: Client = Relationship(sa_relationship=relationship("Client", back_populates="histories"))
    designation: str = Field(default="")
    montant_achat: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    montant_verse: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
    solde_cumule: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(15, 2)))
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
