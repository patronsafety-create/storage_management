import enum
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey, CheckConstraint, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.infrastructure.database import Base 

class TransactionType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    uom = Column(String, nullable=False, default="عدد") # واحد سنجش (Unit of Measure)
    
    transactions = relationship("StockTransaction", back_populates="product")

class Warehouse(Base):
    __tablename__ = "warehouses"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    
    transactions = relationship("StockTransaction", back_populates="warehouse")

class StockTransaction(Base):
    __tablename__ = "stock_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    
    quantity = Column(Float, nullable=False)
    
    batch_number = Column(String, nullable=True)
    reference_document = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="transactions")
    warehouse = relationship("Warehouse", back_populates="transactions")

    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )