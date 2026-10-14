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
    transaction_count = db.query(StockTransaction).count()

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

    is_admin = any(role.name == "Admin" for role in current_user.roles)

    # داده‌های نمودار: موجودی لحظه‌ای کالاها
    stock_balances = InventoryService.calculate_stock_balances(db)
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "tx_count": transaction_count,
            "recent_txs": recent_transactions,
            "pending_txs": pending_transactions,
            "msg": msg,
            "error": error,
            "user": current_user,
            "is_admin": is_admin,
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