from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import Column, Numeric, BigInteger
from sqlmodel import SQLModel, Field

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="operator")
    must_change_password: int = Field(default=0)
    is_active: int = Field(default=1)
    last_login_at: Optional[datetime] = Field(default=None)
    last_password_change_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Client(SQLModel, table=True):
    __tablename__ = "clients"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    opening_credit: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ImportedClientHistory(SQLModel, table=True):
    __tablename__ = "imported_client_history"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    source_file: Optional[str] = Field(default=None)
    entry_date: str
    designation: Optional[str] = Field(default=None)
    debit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    credit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    running_balance: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    imported_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RawMaterial(SQLModel, table=True):
    __tablename__ = "raw_materials"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    unit: str = Field(default="kg")
    stock_qty: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    avg_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_price: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    alert_threshold: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    threshold_qty: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FinishedProduct(SQLModel, table=True):
    __tablename__ = "finished_products"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    default_unit: str = Field(default="kg")
    stock_qty: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_price: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    avg_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    alert_threshold: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movements"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    item_kind: str
    item_id: int
    direction: str
    quantity: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    unit: Optional[str] = Field(default=None)
    stock_before: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    stock_after: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    reason: Optional[str] = Field(default=None)
    reference_type: Optional[str] = Field(default=None)
    reference_id: Optional[int] = Field(default=None)
    created_by_username: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PurchaseDocument(SQLModel, table=True):
    __tablename__ = "purchase_documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="suppliers.id")
    doc_number: str = Field(unique=True)
    total: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    purchase_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SaleDocument(SQLModel, table=True):
    __tablename__ = "sale_documents"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    doc_number: str = Field(unique=True)
    sale_type: str
    total: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    amount_paid: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    balance_due: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Purchase(SQLModel, table=True):
    __tablename__ = "purchases"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: Optional[int] = Field(default=None, foreign_key="suppliers.id")
    document_id: Optional[int] = Field(default=None)
    raw_material_id: Optional[int] = Field(default=None, foreign_key="raw_materials.id")
    finished_product_id: Optional[int] = Field(default=None, foreign_key="finished_products.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit: str = Field(default="kg")
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    purchase_date: date
    notes: Optional[str] = Field(default=None)
    custom_item_name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Sale(SQLModel, table=True):
    __tablename__ = "sales"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit: str
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    sale_type: str
    amount_paid: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    balance_due: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    cost_price_snapshot: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    profit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RawSale(SQLModel, table=True):
    __tablename__ = "raw_sales"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit: str
    unit_price: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    total: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    sale_type: str
    amount_paid: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    balance_due: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    cost_price_snapshot: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    profit_amount: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    sale_date: date
    notes: Optional[str] = Field(default=None)
    custom_item_name: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Payment(SQLModel, table=True):
    __tablename__ = "payments"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: int = Field(foreign_key="clients.id")
    sale_id: Optional[int] = Field(default=None, foreign_key="sales.id")
    raw_sale_id: Optional[int] = Field(default=None, foreign_key="raw_sales.id")
    sale_kind: Optional[str] = Field(default=None)
    payment_type: str = Field(default="versement")
    allocation_meta: Optional[str] = Field(default=None)
    amount: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    payment_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductionBatch(SQLModel, table=True):
    __tablename__ = "production_batches"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    output_quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    production_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    unit_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    production_date: str
    notes: Optional[str] = Field(default=None)

class ProductionBatchItem(SQLModel, table=True):
    __tablename__ = "production_batch_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="production_batches.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    unit_cost_snapshot: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))
    line_cost: Decimal = Field(default=Decimal("0.0000"), sa_column=Column(Numeric(15, 4)))

class SavedRecipe(SQLModel, table=True):
    __tablename__ = "saved_recipes"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    name: str
    notes: Optional[str] = Field(default=None)
    created_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SavedRecipeItem(SQLModel, table=True):
    __tablename__ = "saved_recipe_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    recipe_id: int = Field(foreign_key="saved_recipes.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: Decimal = Field(sa_column=Column(Numeric(15, 4)))
    position: int = Field(default=0)


class Expense(SQLModel, table=True):
    __tablename__ = "expenses"
    
    id: Optional[int] = Field(default=None, sa_column=Column(BigInteger, primary_key=True))
    date: date
    category: str = Field(default="general", index=True)
    description: Optional[str] = Field(default=None)
    amount: float = Field(default=0.0)
    payment_method: str = Field(default="cash")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ClientKey(SQLModel, table=True):
    __tablename__ = "client_keys"
    
    client_id: int = Field(primary_key=True)
    encryption_key: str



