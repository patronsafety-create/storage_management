"""
مدل‌های موجودی انبار
این فایل تنها منبع حقیقت برای جداول products، warehouses و stock_transactions است.
"""
import enum
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey, CheckConstraint, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.infrastructure.database import Base
from src.domain_model.auth_models import User


class TransactionType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class Product(Base):
    """کالاهای قابل نگهداری در انبار"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    uom = Column(String, nullable=False, default="عدد")  # واحد سنجش

    transactions = relationship("StockTransaction", back_populates="product")


class Warehouse(Base):
    """انبارهای سازمان"""
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

    transactions = relationship("StockTransaction", back_populates="warehouse")


class StockTransaction(Base):
    """سند رسید یا حواله انبار"""
    __tablename__ = "stock_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    batch_number = Column(String, nullable=True)
    reference_document = Column(String, nullable=True)
    unit_price = Column(Float, nullable=True, default=0.0)  # قیمت واحد برای کاردکس ریالی
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 🌟 ردیابی ثبت‌کننده سند
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    product = relationship("Product", back_populates="transactions")
    warehouse = relationship("Warehouse", back_populates="transactions")
    created_by = relationship("User", foreign_keys=[created_by_id])

    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )