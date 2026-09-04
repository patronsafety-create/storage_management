from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

# فراخوانی زیرساخت دیتابیس و مدل‌های کاربری
from src.infrastructure.database import get_db
from src.domain_model.user_models import User

# --- تنظیمات امنیتی سیستم ---
SECRET_KEY = "enterprise-erp-super-secret-key-keep-it-safe-and-long"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # انقضای نشست پس از ۲ ساعت

# پیکربندی موتور هش رمز عبور (ارتقا یافته به الگوریتم قدرتمند Argon2 بر اساس استاندارد OWASP)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")

# ==========================================
# بخش اول: توابع کمکی امنیتی (Security Utils)
# ==========================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """بررسی تطابق رمز عبور ساده با هش موجود در دیتابیس"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """تولید هش یک‌طرفه از رمز عبور برای ذخیره در دیتابیس"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """تولید توکن رمزنگاری‌شده JWT برای نشست کاربری"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# وابستگی (Dependency) برای استخراج و اعتبارسنجی کاربر فعلی از روی کوکی مرورگر
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    # خواندن توکن از کوکی‌های امن مرورگر
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


# ==========================================
# بخش دوم: کنترلرهای رابط کاربری ورود و خروج
# ==========================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    """رندر کردن فرم ورود"""
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={"request": request, "error": error}
    )

@router.post("/login")
async def process_login(
    request: Request,
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """اعتبارسنجی اطلاعات فرم و ایجاد نشست امن"""
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "error": "نام کاربری یا رمز عبور اشتباه است."},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
        
    if not user.is_active:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "error": "حساب کاربری شما غیرفعال شده است."},
            status_code=status.HTTP_403_FORBIDDEN
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )

    redirect_response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    
    return redirect_response

@router.get("/logout")
async def logout(response: Response):
    """خروج سیستم و انقضای نشست"""
    redirect_response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.delete_cookie("access_token")
    return redirect_response