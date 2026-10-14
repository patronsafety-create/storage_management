from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.infrastructure.database import get_db
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import Product, StockTransaction, Warehouse
from src.services.inventory_service import InventoryService
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(prefix="/inventory/alerts", tags=["Inventory Alerts"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("", response_class=HTMLResponse)
async def view_stock_alerts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """داشبورد هوشمند هشدارهای موجودی، نقطه سفارش و تحلیل کالاهای راکد (Dead Stock)"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)
    products = db.query(Product).filter_by(is_active=True).all()
    
    out_of_stock = []
    low_stock = []
    over_stock = []
    dead_stock = []

    now = datetime.now()
    thirty_days_ago = now - timedelta(days=30)

    for p in products:
        total_balance = InventoryService.get_total_stock_all_warehouses(db, p.id)
        
        # آخرین تراکنش کالا
        last_tx = (
            db.query(StockTransaction)
            .filter(StockTransaction.product_id == p.id)
            .order_by(StockTransaction.created_at.desc())
            .first()
        )

        item_data = {
            "product": p,
            "current_balance": total_balance,
            "min_stock": p.min_stock or 0.0,
            "reorder_point": p.reorder_point or 0.0,
            "max_stock": p.max_stock or 0.0,
            "last_movement": last_tx.created_at if last_tx else None,
            "days_since_last_tx": (now - last_tx.created_at.replace(tzinfo=None)).days if last_tx and last_tx.created_at else None
        }

        # ۱. اتمام موجودی
        if total_balance <= 0.001:
            out_of_stock.append(item_data)
        # ۲. زیر نقطه سفارش
        elif p.reorder_point and total_balance <= p.reorder_point:
            low_stock.append(item_data)
        
        # ۳. مازاد موجودی
        if p.max_stock and p.max_stock > 0 and total_balance > p.max_stock:
            over_stock.append(item_data)

        # ۴. کالاهای راکد (Dead Stock): بدون گردش در ۳۰ روز گذشته یا بدون هرگونه تراکنش
        if not last_tx or (last_tx.created_at and last_tx.created_at.replace(tzinfo=None) < thirty_days_ago):
            dead_stock.append(item_data)

    return templates.TemplateResponse(
        request=request,
        name="alerts.html",
        context={
            "request": request,
            "out_of_stock": out_of_stock,
            "low_stock": low_stock,
            "over_stock": over_stock,
            "dead_stock": dead_stock,
            "total_alerts": len(out_of_stock) + len(low_stock),
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/badge", response_class=JSONResponse)
async def get_alerts_badge_count(db: Session = Depends(get_db)):
    """وب‌سرویس دریافت سریع تعداد هشدارهای بحرانی جهت نمایش روی زنگوله نوبار"""
    products = db.query(Product).filter_by(is_active=True).all()
    count = 0
    for p in products:
        total_balance = InventoryService.get_total_stock_all_warehouses(db, p.id)
        if total_balance <= 0.001 or (p.reorder_point and total_balance <= p.reorder_point):
            count += 1
    return {"alert_count": count}
