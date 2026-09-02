import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
import jwt

# تنظیمات امنیتی کلان سیستم
# نکته معماری: در محیط عملیاتی (Production) این کلید باید حتماً از طریق متغیرهای محیطی سرور تزریق شود
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_super_hard_to_guess_key_for_erp_12345")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # اعتبار توکن: یک روز (مناسب برای سیستم‌های داخلی ERP)

# پیکربندی موتور هش رمز عبور با استفاده از الگوریتم ایمن Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """
    تولید هش یک‌طرفه و غیرقابل بازگشت از رمز عبور خام
    """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    بررسی تطابق رمز عبور وارد شده توسط کاربر با هش ذخیره شده در دیتابیس
    """
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    تولید توکن رمزنگاری‌شده (JWT) برای کاربری که با موفقیت وارد سیستم شده است
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # افزودن زمان انقضا (exp) و زمان صدور (iat) به محتوای توکن (Payload)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    
    # امضای توکن با کلید مخفی سرور
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt