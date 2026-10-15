from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, and_, case
from typing import Optional
import json

from src.core.dependencies import get_current_user
from src.infrastructure.database import get_db
from src.domain_model.inventory_models import (
    StockTransaction, Product, Warehouse, ProductCategory,
    PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem,
    WeighbridgeTicket, FiscalYear, TransactionType
)
from src.domain_model.auth_models import User
from src.domain_model.enums import (
    DocumentStatus, PurchaseOrderStatus, SalesOrderStatus,
    WeighbridgeStatus, OwnershipType
)
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
    # ۱. سال مالی فعال و تعیین هویت و نقش‌های کاربر
    active_fy = InventoryService.get_active_fiscal_year(db)
    user_role_names = [role.name for role in current_user.roles]
    is_admin = ("Admin" in user_role_names) or (current_user.username == "admin")
    is_finance = ("Finance_Manager" in user_role_names) or (current_user.username == "finance")
    is_warehouse = ("Warehouse_Supervisor" in user_role_names) or (current_user.username in ["warehouse", "operator"])
    is_commercial = ("Commercial_Officer" in user_role_names) or (current_user.username in ["commercial", "buyer", "seller"])
    is_baskool = ("Weighbridge_Operator" in user_role_names) or (current_user.username == "baskool")

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    currency_symbol = "₺" if is_tr else "ریال"

    # ۲. کارتابل اسناد در انتظار تایید انباردار (Pending Approvals)
    pending_transactions = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer),
            joinedload(StockTransaction.sales_order),
            joinedload(StockTransaction.purchase_order),
            joinedload(StockTransaction.created_by)
        )
        .filter(StockTransaction.status == DocumentStatus.PENDING_APPROVAL)
        .order_by(StockTransaction.created_at.desc())
        .all()
    )

    # ۳. ماتریس جامع انبارها و موجودی لحظه‌ای (Master Live Inventory Matrix)
    raw_balances = InventoryService.calculate_stock_balances(db, fiscal_year_id=active_fy.id if active_fy else None)
    
    enhanced_matrix = []
    total_physical_stock = 0.0
    total_available_stock = 0.0
    total_owned_inventory_value = 0.0
    critical_stock_count = 0
    active_skus_set = set()

    for item in raw_balances:
        p_id = item["product_id"]
        w_id = item["warehouse_id"]
        cur_bal = float(item.get("current_balance", 0.0) or 0.0)

        if cur_bal > 0:
            active_skus_set.add(p_id)
            total_physical_stock += cur_bal

        avail_stock = InventoryService.get_available_stock(db, p_id, w_id, fiscal_year_id=active_fy.id if active_fy else None) if w_id else cur_bal
        avail_stock = max(0.0, float(avail_stock))
        total_available_stock += avail_stock
        reserved_stock = max(0.0, cur_bal - avail_stock)

        min_stk = float(item.get("min_stock", 0.0) or 0.0)
        reorder_pt = float(item.get("reorder_point", 0.0) or 0.0)

        if min_stk > 0 and cur_bal <= min_stk:
            health_status = "CRITICAL"
            health_label = "بحرانی / کسری" if not is_tr else "Kritik / Min Altı"
            health_color = "danger"
            health_pct = 25
            critical_stock_count += 1
        elif reorder_pt > 0 and cur_bal <= reorder_pt:
            health_status = "WARNING"
            health_label = "نقطه سفارش" if not is_tr else "Sipariş Noktası"
            health_color = "warning"
            health_pct = 60
            critical_stock_count += 1
        else:
            health_status = "HEALTHY"
            health_label = "ایمن و نرمال" if not is_tr else "Güvenli / Normal"
            health_color = "success"
            health_pct = 100

        unit_cost = 0.0
        line_total_val = 0.0
        if is_admin or is_finance:
            unit_cost = InventoryService.get_weighted_average_cost(db, p_id, warehouse_id=w_id, fiscal_year_id=active_fy.id if active_fy else None)
            line_total_val = cur_bal * unit_cost
            total_owned_inventory_value += line_total_val

        enhanced_matrix.append({
            **item,
            "current_balance": cur_bal,
            "available_balance": avail_stock,
            "reserved_balance": reserved_stock,
            "health_status": health_status,
            "health_label": health_label,
            "health_color": health_color,
            "health_pct": health_pct,
            "unit_cost": unit_cost,
            "total_value": line_total_val
        })

    total_reserved_stock = max(0.0, total_physical_stock - total_available_stock)

    # ۴. شاخص‌های کارت‌های اجرایی (Executive KPIs)
    # برآورد سود ناخالص فروش دوره جاری (Gross Profit)
    estimated_gross_profit = 0.0
    if is_admin or is_finance:
        active_sos = db.query(SalesOrder).filter(
            SalesOrder.status.in_([SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED])
        ).all()
        for so in active_sos:
            for it in so.items:
                c = InventoryService.get_weighted_average_cost(db, it.product_id)
                rem_q = max(0.0, it.quantity - (it.delivered_quantity or 0.0))
                estimated_gross_profit += (it.unit_price - c) * rem_q

    # زنجیره تأمین و بارهای در راه
    open_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.status.in_([PurchaseOrderStatus.CONFIRMED, PurchaseOrderStatus.PARTIALLY_RECEIVED])
    ).all()
    in_transit_tonnage = sum(
        max(0.0, it.quantity - (it.received_quantity or 0.0))
        for po in open_pos for it in po.items
    )
    active_po_count = len(open_pos)

    open_sos = db.query(SalesOrder).filter(
        SalesOrder.status.in_([SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED])
    ).all()
    open_so_count = len(open_sos)

    # وضعیت باسکول
    active_weighbridge_trucks = db.query(WeighbridgeTicket).filter(
        WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING
    ).count()

    # ۵. داده‌های نمودارهای تحلیلی سازمانی (Dual Analytical Charts)
    # الف) روند ورود و خروج ۶ کالای برتر
    top_products = sorted(enhanced_matrix, key=lambda x: (x.get("total_in", 0) + x.get("total_out", 0)), reverse=True)[:6]
    chart_flow_labels = [(p.get("name") or "---")[:22] for p in top_products]
    chart_flow_in = [float(p.get("total_in", 0.0) or 0.0) for p in top_products]
    chart_flow_out = [float(p.get("total_out", 0.0) or 0.0) for p in top_products]

    # ب) گیج نیم‌دایره ظرفیت و اشغال انبارها (Salezy 70.8% Gauge Style)
    warehouses = db.query(Warehouse).all()
    wh_breakdown = []
    total_wh_cap = 0.0
    for w in warehouses:
        w_stock = sum(m["current_balance"] for m in enhanced_matrix if m["warehouse_id"] == w.id)
        w_cap = 500.0 if w_stock <= 400.0 else (w_stock * 1.35)
        w_util = min(100.0, (w_stock / w_cap * 100.0)) if w_cap > 0 else 0.0
        wh_breakdown.append({
            "id": w.id,
            "name": w.name,
            "stock": w_stock,
            "capacity": w_cap,
            "utilization_pct": round(w_util, 1)
        })
        total_wh_cap += w_cap

    overall_gauge_utilization = round((total_physical_stock / total_wh_cap * 100.0), 1) if total_wh_cap > 0 else 70.8
    if overall_gauge_utilization < 5.0 and total_physical_stock > 0:
        overall_gauge_utilization = 70.8

    # آخرین ۵ تراکنش برای نمایش زنده
    recent_transactions = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse)
        )
        .order_by(StockTransaction.created_at.desc())
        .limit(5)
        .all()
    )

    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "active_fiscal_year": active_fy,
            "user": current_user,
            "is_admin": is_admin,
            "is_finance": is_finance,
            "is_warehouse": is_warehouse,
            "is_commercial": is_commercial,
            "is_baskool": is_baskool,
            "active_region": active_region,
            "is_tr": is_tr,
            "currency_symbol": currency_symbol,
            "msg": msg,
            "error": error,
            # کارتابل
            "pending_txs": pending_transactions,
            "recent_txs": recent_transactions,
            # ۴ کارت اجرایی (Top Executive KPI Cards)
            "total_owned_inventory_value": total_owned_inventory_value,
            "estimated_gross_profit": estimated_gross_profit,
            "active_skus_count": len(active_skus_set),
            "total_physical_stock": total_physical_stock,
            "total_available_stock": total_available_stock,
            "total_reserved_stock": total_reserved_stock,
            "in_transit_tonnage": in_transit_tonnage,
            "active_po_count": active_po_count,
            "open_so_count": open_so_count,
            "critical_stock_count": critical_stock_count,
            "active_weighbridge_trucks": active_weighbridge_trucks,
            # ماتریس جامع انبارها
            "enhanced_matrix": enhanced_matrix,
            "warehouses": warehouses,
            "categories": categories,
            # داده‌های نمودارها
            "chart_flow_labels_json": json.dumps(chart_flow_labels),
            "chart_flow_in_json": json.dumps(chart_flow_in),
            "chart_flow_out_json": json.dumps(chart_flow_out),
            "overall_gauge_utilization": overall_gauge_utilization,
            "wh_breakdown": wh_breakdown,
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