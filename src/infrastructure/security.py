import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt
from dotenv import load_dotenv

load_dotenv()

# کلید مخفی و الگوریتم — از .env خوانده می‌شوند
SECRET_KEY = os.getenv("SECRET_KEY", "enterprise-erp-ultra-secret-key-2026-storage-management-do-not-share")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # اعتبار توکن: یک روز

# پیکربندی موتور هش با الگوریتم argon2 (امن‌ترین گزینه فعلی)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """تولید هش یک‌طرفه از رمز عبور خام"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """بررسی تطابق رمز عبور با هش ذخیره‌شده"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """تولید JWT امضاشده با کلید مخفی سرور"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)