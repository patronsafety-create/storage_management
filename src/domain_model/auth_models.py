from sqlalchemy import String, Boolean, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

# فراخوانی Base اصلی پروژه برای یکپارچگی مایگریشن‌ها
from src.domain_model.models import Base

class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=True)
    # ذخیره دسترسی‌ها به صورت آرایه‌ای از رشته‌ها برای انعطاف‌پذیری بالا
    permissions: Mapped[list] = mapped_column(JSONB, default=list, server_default='[]')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # ارتباط یک‌به‌چند با کاربران
    users: Mapped[list["User"]] = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # فیلد تلگرام برای ارسال هشدارهای سیستمی و نقطه سفارش به مدیران
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # محدودیت RESTRICT: اجازه حذف نقشی که کاربر دارد را در سطح دیتابیس نمی‌دهد
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    role: Mapped["Role"] = relationship("Role", back_populates="users")