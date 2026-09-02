import uuid
from datetime import datetime
from typing import List
from sqlalchemy import String, Boolean, ForeignKey, DateTime, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

# ---------------------------------------------------------
# جدول‌های واسط (Association Tables) برای روابط چند-به-چند
# ---------------------------------------------------------

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)

class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[str] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[str] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


# ---------------------------------------------------------
# موجودیت‌های اصلی امنیت و مدیریت دسترسی
# ---------------------------------------------------------

class User(Base):
    """موجودیت کاربران سیستم"""
    __tablename__ = "users"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    # ارتباط با نقش‌ها
    roles: Mapped[List["Role"]] = relationship(secondary="user_roles", back_populates="users")

class Role(Base):
    """موجودیت نقش‌های سازمانی (مانند: مدیر عامل، سرپرست انبار)"""
    __tablename__ = "roles"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False) # کلید سیستمی: warehouse_manager
    title: Mapped[str] = mapped_column(String(100), nullable=False) # عنوان نمایشی: سرپرست انبار

    # ارتباط با کاربران و مجوزها
    users: Mapped[List["User"]] = relationship(secondary="user_roles", back_populates="roles")
    permissions: Mapped[List["Permission"]] = relationship(secondary="role_permissions", back_populates="roles")

class Permission(Base):
    """موجودیت مجوزهای ریزدانه (مانند: خواندن سفارش، تایید رسید)"""
    __tablename__ = "permissions"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False) # کلید سیستمی: order:read
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    # ارتباط با نقش‌ها
    roles: Mapped[List["Role"]] = relationship(secondary="role_permissions", back_populates="permissions")