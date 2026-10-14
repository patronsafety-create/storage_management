from fastapi import APIRouter, Depends, status, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Optional

from src.infrastructure.database import get_db
from src.infrastructure.security import (
    verify_password, get_password_hash,
    create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
)
from src.domain_model.auth_models import User
from src.core.dependencies import get_current_user, require_admin
from src.core.localization.regions import (
    Region, REGIONS, get_active_region, get_locale_dict, get_translation
)

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")


@router.get("/set-region/{region_code}")
async def set_active_region(request: Request, region_code: str, next: Optional[str] = None):
    """تغییر منطقه فعال (ایران / ترکیه) و ذخیره در کوکی مرورگر"""
    code = region_code.upper().strip()
    if code not in REGIONS:
        code = Region.IR

    redirect_url = next or request.headers.get("referer") or "/dashboard"
    # اطمینان از امنیت مسیر ریدایرکت
    if not redirect_url.startswith("/") and not ("://" in redirect_url):
        redirect_url = "/dashboard"

    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key="nexus_region",
        value=code,
        max_age=365 * 24 * 3600,
        httponly=False,
        samesite="lax"
    )
    response.set_cookie(
        key="nexus_lang",
        value=REGIONS[code].default_lang,
        max_age=365 * 24 * 3600,
        httponly=False,
        samesite="lax"
    )
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    active_region = get_active_region(request)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "error": error,
            "region": active_region,
            "all_regions": REGIONS
        }
    )


@router.post("/login")
async def process_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    region: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    active_region = get_active_region(request)
    if region and region.upper().strip() in REGIONS:
        active_region = REGIONS[region.upper().strip()]

    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.hashed_password):
        error_msg = "Kullanıcı adı veya şifre hatalı." if active_region.code == Region.TR else "نام کاربری یا رمز عبور اشتباه است."
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "error": error_msg,
                "region": active_region,
                "all_regions": REGIONS
            },
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        error_msg = "Kullanıcı hesabınız devre dışı bırakılmıştır." if active_region.code == Region.TR else "حساب کاربری شما غیرفعال شده است."
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "request": request,
                "error": error_msg,
                "region": active_region,
                "all_regions": REGIONS
            },
            status_code=status.HTTP_403_FORBIDDEN
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    redirect_response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax"
    )
    # ثبت کوکی‌های منطقه و زبان کاربر
    redirect_response.set_cookie(
        key="nexus_region",
        value=active_region.code,
        max_age=365 * 24 * 3600,
        httponly=False,
        samesite="lax"
    )
    redirect_response.set_cookie(
        key="nexus_lang",
        value=active_region.default_lang,
        max_age=365 * 24 * 3600,
        httponly=False,
        samesite="lax"
    )
    return redirect_response


@router.get("/logout")
async def logout():
    """خروج امن: پاکسازی کوکی و کش مرورگر"""
    redirect_response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    redirect_response.delete_cookie("access_token")
    redirect_response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    redirect_response.headers["Pragma"] = "no-cache"
    redirect_response.headers["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return redirect_response