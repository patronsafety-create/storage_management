from fastapi import APIRouter, Depends, status, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt

# 🌟 فراخوانی وابستگی‌ها و کلیدهای امنیتی مستقیماً از هسته مرکزی (Core)
from src.core.dependencies import get_db, SECRET_KEY, ALGORITHM
from src.domain_model.user_models import User

# تنظیمات انقضای نشست
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# پیکربندی موتور هش رمز عبور (Argon2)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")

# ==========================================
# توابع کمکی امنیتی (تولید توکن و هش رمز عبور)
# ==========================================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    # استفاده از کلیدهای امنیتی ایمپورت شده از dependencies
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# 💡 نکته معماری: تابع get_current_user از اینجا حذف شد، 
# زیرا به طور متمرکز در core/dependencies.py قرار گرفته است.

# ==========================================
# کنترلرهای رابط کاربری ورود و خروج
# ==========================================
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
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
async def logout():
    """
    خروج امن از سیستم: 
    پاکسازی توکن و جلوگیری از دسترسی به صفحات کش شده پس از خروج
    """
    redirect_response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    
    # حذف کوکی نشست (Session Token) از مرورگر کلاینت
    redirect_response.delete_cookie("access_token")
    
    # اعمال هدرهای امنیتی سخت‌گیرانه برای پاکسازی حافظه پنهان (Cache) مرورگر
    redirect_response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    redirect_response.headers["Pragma"] = "no-cache"
    redirect_response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    
    return redirect_response