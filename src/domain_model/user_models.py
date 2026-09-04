from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

# فراخوانی Base از زیرساخت دیتابیس
from src.infrastructure.database import Base

# جدول واسط برای ایجاد ارتباط چند-به-چند بین کاربران و نقش‌ها
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)

class Role(Base):
    """
    جدول نقش‌های سیستمی (مانند Admin, Warehouse_Operator)
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    # برقراری ارتباط با جدول کاربران
    users = relationship("User", secondary=user_roles, back_populates="roles")

class User(Base):
    """
    جدول اطلاعات پایه و امنیتی کاربران
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    
    # ما هرگز رمز عبور را به صورت متن ساده (Plain-text) ذخیره نمی‌کنیم
    # این فیلد در آینده میزبان هش‌های امنیتی (مثل Bcrypt) خواهد بود
    hashed_password = Column(String, nullable=False)
    
    full_name = Column(String, nullable=False)
    
    # مکانیزم امنیتی برای غیرفعال کردن کاربران (Soft Delete) به جای حذف فیزیکی آن‌ها
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # برقراری ارتباط با جدول نقش‌ها
    roles = relationship("Role", secondary=user_roles, back_populates="users")