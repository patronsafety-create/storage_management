from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Numeric, ForeignKey, DateTime, func, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class Warehouse(Base):
    __tablename__ = "warehouses"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Product(Base):
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # ذخیره تا 10 مشخصه متغیر (مثل رنگ، ابعاد، تاریخ انقضا و غیره) با قابلیت ایندکس‌گذاری
    attributes: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, server_default='{}')
    reorder_point: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PriceList(Base):
    __tablename__ = "price_lists"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False) # e.g., USD, TRY
    # استفاده از Numeric برای جلوگیری از خطای Float در محاسبات مالی
    price: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # جلوگیری از ثبت قیمت منفی یا صفر در سطح دیتابیس
    __table_args__ = (
        CheckConstraint('price > 0', name='check_positive_price'),
    )

    product: Mapped["Product"] = relationship("Product", backref="price_lists")