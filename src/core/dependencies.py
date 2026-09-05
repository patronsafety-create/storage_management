from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from jose import JWTError, jwt

# فراخوانی لایه‌های زیرساخت و دامنه
from src.infrastructure.database import SessionLocal
from src.domain_model.user_models import User

# --- تنظیمات امنیتی سیستم ---
# در محیط عملیاتی، این کلیدها باید در فایل محیطی (.env) مخفی شوند
SECRET_KEY = "enterprise-erp-super-secret-key-keep-it-safe-and-long"
ALGORITHM = "HS256"

def get_db():
    """
    تزریق وابستگی (Dependency Injection) برای مدیریت امن نشست‌های پایگاه‌داده
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    بررسی توکن JWT، اعتبارسنجی هویت و استخراج کاربر جاری از دیتابیس
    این تابع به عنوان قفل امنیتی در سراسر سیستم استفاده خواهد شد.
    """
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