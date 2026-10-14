"""
مدیریت کاربران (فقط Admin)
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urllib.parse import quote
from typing import Optional

from src.core.dependencies import get_db, require_admin, get_current_user
from src.domain_model.auth_models import User, Role
from src.infrastructure.security import get_password_hash

from src.core.localization.regions import localize_display_name, get_active_region

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(require_admin)]
)
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    msg: Optional[str] = None,
    error: Optional[str] = None
):
    users = db.query(User).order_by(User.id).all()
    roles = db.query(Role).order_by(Role.name).all()
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="users.html",
        context={
            "request": request,
            "users": users,
            "roles": roles,
            "user": current_user,
            "msg": msg,
            "error": error,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.post("/users")
async def create_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role_id: int = Form(...),
    db: Session = Depends(get_db)
):
    try:
        role = db.query(Role).filter(Role.id == role_id).first()
        if not role:
            return RedirectResponse(url="/admin/users?error=" + quote("نقش انتخاب شده وجود ندارد"), status_code=303)

        new_user = User(
            username=username.strip(),
            hashed_password=get_password_hash(password),
            full_name=full_name.strip(),
            is_active=True
        )
        new_user.roles.append(role)
        db.add(new_user)
        db.commit()
        return RedirectResponse(url="/admin/users?msg=" + quote(f"کاربر '{username}' با موفقیت ایجاد شد"), status_code=303)
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/admin/users?error=" + quote("این نام کاربری از قبل در سیستم وجود دارد"), status_code=303)


@router.post("/users/{user_id}/toggle")
async def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if user_id == current_user.id:
        return RedirectResponse(url="/admin/users?error=" + quote("نمی‌توانید حساب خودتان را غیرفعال کنید"), status_code=303)

    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        return RedirectResponse(url="/admin/users?error=" + quote("کاربر یافت نشد"), status_code=303)

    target.is_active = not target.is_active
    db.commit()
    status_text = "فعال" if target.is_active else "غیرفعال"
    return RedirectResponse(url="/admin/users?msg=" + quote(f"کاربر '{target.username}' {status_text} شد"), status_code=303)
