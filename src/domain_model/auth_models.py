"""
مدل‌های احراز هویت و مدیریت دسترسی (RBAC)
این فایل تنها منبع حقیقت (Single Source of Truth) برای جداول users و roles است.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Table
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.infrastructure.database import Base

# جدول واسط چند-به-چند بین کاربران و نقش‌ها
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
)


class Role(Base):
    """جدول نقش‌های سیستمی (Admin, Warehouse_Operator, ...)"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)

    users = relationship("User", secondary=user_roles, back_populates="roles")


class User(Base):
    """جدول کاربران سیستم"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    roles = relationship("Role", secondary=user_roles, back_populates="users")