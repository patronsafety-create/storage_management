from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from src.core.dependencies import get_current_user
from src.infrastructure.database import get_db
from src.domain_model.inventory_models import StockTransaction, ProductCategory
from src.domain_model.auth_models import User
from src.domain_model.enums import DocumentStatus
from src.services.inventory_service import InventoryService
from src.core.localization.regions import localize_display_name, get_active_region

router = APIRouter(tags=["UI"], dependencies=[Depends(get_current_user)])
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # ۱. سال مالی فعال و شمارش اسناد تأیید شده (APPROVED) دوره جاری
    active_fy = InventoryService.get_active_fiscal_year(db)
    if active_fy:
        approved_tx_count = db.query(StockTransaction).filter(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.fiscal_year_id == active_fy.id
        ).count()
    else:
        approved_tx_count = db.query(StockTransaction).filter(
            StockTransaction.status == DocumentStatus.APPROVED
        ).count()

    recent_transactions = (
        db.query(StockTransaction)
        .order_by(StockTransaction.created_at.desc())
        .limit(5)
        .all()
    )

    pending_transactions = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer),
            joinedload(StockTransaction.created_by)
        )
        .filter(StockTransaction.status == DocumentStatus.PENDING_APPROVAL)
        .order_by(StockTransaction.created_at.desc())
        .all()
    )

    # تعیین نقش‌ها
    user_role_names = [role.name for role in current_user.roles]
    is_admin = ("Admin" in user_role_names) or (current_user.username == "admin")
    is_finance = ("Finance_Manager" in user_role_names) or (current_user.username == "finance")
    is_warehouse = ("Warehouse_Supervisor" in user_role_names) or (current_user.username in ["warehouse", "operator"])
    is_commercial = ("Commercial_Officer" in user_role_names) or (current_user.username in ["commercial", "buyer", "seller"])
    is_baskool = ("Weighbridge_Operator" in user_role_names) or (current_user.username == "baskool")

    # نام نقش فارسی
    if is_admin:
        user_role_fa = "مدیر ارشد سیستم"
        user_role_tr = "Sistem Yöneticisi"
    elif is_finance:
        user_role_fa = "مدیر مالی و حسابداری"
        user_role_tr = "Mali ve Muhasebe Müdürü"
    elif is_warehouse:
        user_role_fa = "سرپرست انبار"
        user_role_tr = "Depo Amiri"
    elif is_commercial:
        user_role_fa = "کارشناس بازرگانی"
        user_role_tr = "Ticaret Uzmanı"
    elif is_baskool:
        user_role_fa = "اپراتور باسکول دیجیتال"
        user_role_tr = "Kantar Operatörü"
    else:
        user_role_fa = current_user.roles[0].description if current_user.roles else "کاربر سیستم"
        user_role_tr = current_user.roles[0].name if current_user.roles else "Kullanıcı"

    # ۲. داده‌های موجودی و شمارش اقلام دارای موجودی مثبت (current_balance > 0)
    stock_balances = InventoryService.calculate_stock_balances(db)
    positive_stock_items_count = sum(1 for item in stock_balances if item.get("current_balance", 0) > 0)

    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "tx_count": approved_tx_count,
            "positive_items_count": positive_stock_items_count,
            "user_role_fa": user_role_tr if is_tr else user_role_fa,
            "active_fiscal_year": active_fy,
            "recent_txs": recent_transactions,
            "pending_txs": pending_transactions,
            "msg": msg,
            "error": error,
            "user": current_user,
            "is_admin": is_admin,
            "is_finance": is_finance,
            "is_warehouse": is_warehouse,
            "is_commercial": is_commercial,
            "is_baskool": is_baskool,
            "stock_balances": stock_balances,
            "categories": categories,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.get("/guide", response_class=HTMLResponse)
async def user_guide(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """کاتالوگ فنی و راهنمای جامع کاربری سامانه نکسوس‌پور"""
    is_admin = any(role.name == "Admin" for role in current_user.roles)
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="user_guide.html",
        context={
            "request": request,
            "user": current_user,
            "is_admin": is_admin,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )