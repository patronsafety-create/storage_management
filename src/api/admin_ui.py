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

from src.core.dependencies import get_db, require_admin, get_current_user, allow_roles
from src.domain_model.auth_models import User, Role
from src.infrastructure.security import get_password_hash
from src.core.version import load_release_history, get_current_version, bump_version

from src.core.localization.regions import localize_display_name, get_active_region

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("/changelog", response_class=HTMLResponse)
async def view_changelog(
    request: Request,
    current_user: User = Depends(allow_roles("Admin", "Finance_Manager")),
    msg: Optional[str] = None,
    error: Optional[str] = None
):
    """مشاهده تاریخچه نگارش‌ها و انتشار (Interactive Release Notes Timeline)"""
    history = load_release_history()
    current_version = get_current_version()
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    is_admin = any(r.name == "Admin" for r in current_user.roles) or current_user.username == "admin"

    return templates.TemplateResponse(
        request=request,
        name="changelog.html",
        context={
            "request": request,
            "user": current_user,
            "is_admin": is_admin,
            "history": history,
            "current_version": current_version,
            "msg": msg,
            "error": error,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("/changelog/bump")
async def handle_bump_version(
    request: Request,
    bump_type: str = Form("patch"),
    title: str = Form(...),
    arch_notes: Optional[str] = Form(None),
    sec_notes: Optional[str] = Form(None),
    fin_notes: Optional[str] = Form(None),
    admin: User = Depends(require_admin)
):
    """ثبت نسخه جدید سازمانی و انتشار یادداشت تغییرات"""
    categories = {}
    if arch_notes and arch_notes.strip():
        categories["🚀 Architecture & Features"] = [n.strip() for n in arch_notes.strip().split("\n") if n.strip()]
    if sec_notes and sec_notes.strip():
        categories["🛡️ Security & RBAC Hardening"] = [n.strip() for n in sec_notes.strip().split("\n") if n.strip()]
    if fin_notes and fin_notes.strip():
        categories["⚖️ Financial & Tax Engine"] = [n.strip() for n in fin_notes.strip().split("\n") if n.strip()]

    if not categories:
        categories["🚀 Architecture & Features"] = [title.strip()]

    new_ver = bump_version(bump_type=bump_type, title=title, changes=categories)
    return RedirectResponse(
        url=f"/admin/changelog?msg={quote(f'نسخه {new_ver} با موفقیت در تاریخچه انتشارات ثبت گردید')}",
        status_code=303
    )


@router.get("/users", response_class=HTMLResponse)
async def list_users(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
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
