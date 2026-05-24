from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship

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
    opening_credit: float = Field(default=0.0)
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
    debit_amount: float = Field(default=0.0)
    credit_amount: float = Field(default=0.0)
    running_balance: float = Field(default=0.0)
    imported_by_user_id: Optional[int] = Field(default=None, foreign_key="users.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RawMaterial(SQLModel, table=True):
    __tablename__ = "raw_materials"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    unit: str = Field(default="kg")
    stock_qty: float = Field(default=0.0)
    avg_cost: float = Field(default=0.0)
    sale_price: float = Field(default=0.0)
    alert_threshold: float = Field(default=0.0)
    threshold_qty: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FinishedProduct(SQLModel, table=True):
    __tablename__ = "finished_products"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    default_unit: str = Field(default="kg")
    stock_qty: float = Field(default=0.0)
    sale_price: float = Field(default=0.0)
    avg_cost: float = Field(default=0.0)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class StockMovement(SQLModel, table=True):
    __tablename__ = "stock_movements"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    item_kind: str
    item_id: int
    direction: str
    quantity: float = Field(default=0.0)
    unit: Optional[str] = Field(default=None)
    stock_before: float = Field(default=0.0)
    stock_after: float = Field(default=0.0)
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
    total: float = Field(default=0.0)
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
    total: float = Field(default=0.0)
    amount_paid: float = Field(default=0.0)
    balance_due: float = Field(default=0.0)
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
    quantity: float
    unit: str = Field(default="kg")
    unit_price: float
    total: float
    purchase_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Sale(SQLModel, table=True):
    __tablename__ = "sales"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    client_id: Optional[int] = Field(default=None, foreign_key="clients.id")
    document_id: Optional[int] = Field(default=None)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    quantity: float
    unit: str
    unit_price: float
    total: float
    sale_type: str
    amount_paid: float = Field(default=0.0)
    balance_due: float = Field(default=0.0)
    cost_price_snapshot: float = Field(default=0.0)
    profit_amount: float = Field(default=0.0)
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
    quantity: float
    unit: str
    unit_price: float
    total: float
    sale_type: str
    amount_paid: float = Field(default=0.0)
    balance_due: float = Field(default=0.0)
    cost_price_snapshot: float = Field(default=0.0)
    profit_amount: float = Field(default=0.0)
    sale_date: date
    notes: Optional[str] = Field(default=None)
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
    amount: float
    payment_date: date
    notes: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductionBatch(SQLModel, table=True):
    __tablename__ = "production_batches"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    finished_product_id: int = Field(foreign_key="finished_products.id")
    output_quantity: float
    production_cost: float = Field(default=0.0)
    unit_cost: float = Field(default=0.0)
    production_date: str
    notes: Optional[str] = Field(default=None)

class ProductionBatchItem(SQLModel, table=True):
    __tablename__ = "production_batch_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="production_batches.id")
    raw_material_id: int = Field(foreign_key="raw_materials.id")
    quantity: float
    unit_cost_snapshot: float = Field(default=0.0)
    line_cost: float = Field(default=0.0)

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
    quantity: float
    position: int = Field(default=0)
