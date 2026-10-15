from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from src.infrastructure.database import get_db
from src.infrastructure.security import SECRET_KEY, ALGORITHM
from src.domain_model.auth_models import User


async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """گارد امنیتی: خواندن کوکی، اعتبارسنجی JWT، استخراج کاربر جاری"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed")

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user


def allow_roles(*allowed_roles: str):
    """
    گارد مرکزی امنیتی مبتنی بر نقش (RBAC)
    نقش Admin همواره دسترسی کامل و نامحدود دارد.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = [role.name for role in current_user.roles]
        
        # ۱. ادمین همیشه دسترسی کامل دارد
        if "Admin" in user_role_names or current_user.username == "admin":
            return current_user
        
        # ۲. بررسی سایر نقش‌ها و سازگاری با نگاشت نقش‌های کاربر
        for role in allowed_roles:
            if role in user_role_names:
                return current_user
            if role == "Commercial_Officer" and current_user.username in ["commercial", "buyer", "seller"]:
                return current_user
            if role == "Finance_Manager" and current_user.username == "finance":
                return current_user
            if role == "Warehouse_Supervisor" and current_user.username in ["warehouse", "operator"]:
                return current_user
            if role == "Weighbridge_Operator" and current_user.username == "baskool":
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"دسترسی غیرمجاز. این بخش نیازمند دسترسی یکی از نقش‌های {', '.join(allowed_roles)} می‌باشد."
        )
    return role_checker


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """قفل RBAC: فقط کاربران با نقش Admin مجاز هستند"""
    if not any(role.name == "Admin" for role in current_user.roles) and current_user.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی غیرمجاز. این عملیات فقط برای مدیر کل سیستم امکان‌پذیر است."
        )
    return current_user