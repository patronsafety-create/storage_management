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

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")


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