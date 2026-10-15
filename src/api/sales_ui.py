from typing import Optional
from urllib.parse import quote
from datetime import datetime
import json

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from src.infrastructure.database import get_db
from src.core.dependencies import allow_roles
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import (
    SalesOrder,
    SalesOrderItem,
    Customer,
    Product,
    Warehouse,
    StockTransaction,
    TransactionType,
    WeighbridgeTicket
)
from src.domain_model.enums import SalesOrderStatus, DocumentStatus, TransactionSource, WeighbridgeStatus
from src.services.audit_service import AuditService
from src.services.tax_service import TaxService
from src.services.inventory_service import InventoryService
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(
    prefix="/sales",
    tags=["Sales Orders"],
    dependencies=[Depends(allow_roles("Admin", "Commercial_Officer", "Finance_Manager"))]
)
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("", response_class=HTMLResponse)
async def list_sales_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None),
    customer_filter: Optional[int] = Query(None)
):
    """لیست و داشبورد سفارشات فروش کالا به مشتریان و پیمانکاران"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    query = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.customer),
            joinedload(SalesOrder.created_by),
            joinedload(SalesOrder.items).joinedload(SalesOrderItem.product)
        )
        .order_by(SalesOrder.created_at.desc())
    )

    if status_filter:
        query = query.filter(SalesOrder.status == SalesOrderStatus[status_filter])
    if customer_filter:
        query = query.filter(SalesOrder.customer_id == customer_filter)

    orders = query.all()
    customers = db.query(Customer).filter_by(is_active=True).order_by(Customer.name).all()

    # شاخص‌های آماری فروش
    total_orders = len(orders)
    pending_delivery = sum(1 for o in orders if o.status in (SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED))
    completed_orders = sum(1 for o in orders if o.status == SalesOrderStatus.COMPLETED)

    total_value = sum(o.total_amount for o in orders)

    # تعیین نقش‌ها جهت نمایش حاشیه سود
    user_role_names = [role.name for role in current_user.roles]
    is_admin = ("Admin" in user_role_names) or (current_user.username == "admin")
    is_finance = ("Finance_Manager" in user_role_names) or (current_user.username == "finance")

    # محاسبه سود ناخالص لحظه‌ای سفارشات فروش (فقط برای مدیر ارشد و مدیر مالی)
    orders_profit_map = {}
    total_sales_profit = 0.0
    if is_admin or is_finance:
        for o in orders:
            o_profit = 0.0
            for it in o.items:
                c = InventoryService.get_weighted_average_cost(db, it.product_id)
                o_profit += (it.unit_price - c) * it.quantity
            o_subtotal = o.subtotal_amount or sum(it.total_price for it in o.items)
            o_margin = (o_profit / o_subtotal * 100.0) if o_subtotal > 0 else 0.0
            total_sales_profit += o_profit
            orders_profit_map[o.id] = {
                "profit": o_profit,
                "margin_pct": round(o_margin, 1)
            }

    return templates.TemplateResponse(
        request=request,
        name="sales.html",
        context={
            "request": request,
            "orders": orders,
            "customers": customers,
            "status_filter": status_filter,
            "customer_filter": customer_filter,
            "total_orders": total_orders,
            "pending_delivery": pending_delivery,
            "completed_orders": completed_orders,
            "total_value": total_value,
            "total_sales_profit": total_sales_profit,
            "orders_profit_map": orders_profit_map,
            "is_admin": is_admin,
            "is_finance": is_finance,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_sales_order_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت پیش‌فاکتور و سفارش فروش جدید (SO)"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    customers = db.query(Customer).filter_by(is_active=True).order_by(Customer.name).all()
    products = db.query(Product).filter_by(is_active=True).order_by(Product.name).all()

    count = db.query(SalesOrder).count() + 1
    generated_so_number = f"SO-TR-{count:04d}" if is_tr else f"SO-1403-{count:04d}"

    product_stocks = {
        p.id: round(InventoryService.get_total_stock_all_warehouses(db, p.id), 3)
        for p in products
    }

    return templates.TemplateResponse(
        request=request,
        name="sales_form.html",
        context={
            "request": request,
            "customers": customers,
            "products": products,
            "product_stocks": product_stocks,
            "generated_so_number": generated_so_number,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_sales_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    so_number: str = Form(...),
    customer_id: int = Form(...),
    delivery_due_date: Optional[str] = Form(None),
    delivery_address: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    product_id: list[int] = Form(...),
    quantity: list[float] = Form(...),
    unit_price: list[float] = Form(...)
):
    """ثبت و ذخیره سفارش فروش با تفکیک توقیف مالیاتی آهن‌آلات و آدرس پروژه تخلیه"""
    try:
        # تشخیص منطقه جغرافیایی سفارش منحصراً از روی کشور مشتری (حذف وابستگی به کوکی مرورگر)
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        is_tr = bool(customer and customer.country_code == "TR")
        region_code = "TR" if is_tr else "IR"

        subtotal = 0.0
        steel_subtotal = 0.0
        has_steel = False
        valid_items_data = []

        for pid, qty, price in zip(product_id, quantity, unit_price):
            if qty > 0:
                line_total = qty * price
                subtotal += line_total
                p = db.query(Product).options(joinedload(Product.category)).filter(Product.id == pid).first()
                if p and TaxService.is_steel_tevkifat_eligible(
                    gtip_code=p.gtip_code,
                    category_code=p.category.code if p.category else None,
                    product_name=p.name
                ):
                    has_steel = True
                    steel_subtotal += line_total
                valid_items_data.append((pid, qty, price, line_total))

        tax_res = TaxService.calculate_tax(
            base_amount=subtotal,
            region_code=region_code,
            is_steel=has_steel,
            steel_base_amount=steel_subtotal
        )

        resolved_delivery_addr = delivery_address.strip() if delivery_address else (customer.address if customer and customer.address else None)

        so = SalesOrder(
            so_number=so_number.strip(),
            customer_id=customer_id,
            delivery_due_date=delivery_due_date.strip() if delivery_due_date else None,
            delivery_address=resolved_delivery_addr,
            status=SalesOrderStatus.CONFIRMED,
            notes=notes.strip() if notes else None,
            subtotal_amount=tax_res.base_amount,
            vat_rate=tax_res.vat_rate,
            vat_amount=tax_res.vat_amount,
            tevkifat_rate=tax_res.tevkifat_rate_str,
            tevkifat_amount=tax_res.tevkifat_amount,
            total_amount=tax_res.total_payable,
            currency="TRY" if is_tr else "IRR",
            created_by_id=current_user.id
        )
        db.add(so)
        db.flush()

        for pid, qty, price, line_total in valid_items_data:
            item = SalesOrderItem(
                sales_order_id=so.id,
                product_id=pid,
                quantity=qty,
                delivered_quantity=0.0,
                unit_price=price,
                total_price=line_total
            )
            db.add(item)

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="SalesOrder",
            entity_id=str(so.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت سفارش فروش {so.so_number} (پایه: {tax_res.base_amount} {tax_res.currency_symbol} - توقیف: {tax_res.tevkifat_amount} - کل: {tax_res.total_payable})"
        )

        return RedirectResponse(
            url=f"/sales/{so.id}?msg=" + quote(f"سفارش فروش {so.so_number} با موفقیت ثبت شد"),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        customers = db.query(Customer).filter_by(is_active=True).all()
        products = db.query(Product).filter_by(is_active=True).all()
        return templates.TemplateResponse(
            request=request,
            name="sales_form.html",
            context={
                "request": request,
                "customers": customers,
                "products": products,
                "error": f"خطا در ثبت سفارش فروش: {str(e)}",
                "generated_so_number": so_number,
                "user": current_user
            },
            status_code=400
        )


@router.get("/{order_id}", response_class=HTMLResponse)
async def view_sales_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مشاهده جزئیات سفارش فروش، پیشرفت تحویل و فرم صدور حواله خروج انبار"""
    so = (
        db.query(SalesOrder)
        .options(
            joinedload(SalesOrder.customer),
            joinedload(SalesOrder.created_by),
            joinedload(SalesOrder.items).joinedload(SalesOrderItem.product)
        )
        .filter(SalesOrder.id == order_id)
        .first()
    )
    if not so:
        raise HTTPException(status_code=404, detail="سفارش فروش یافت نشد")

    warehouses = db.query(Warehouse).all()
    subtotal = so.subtotal_amount or sum(item.total_price for item in so.items)
    is_tr = (so.currency == "TRY") or (so.customer and so.customer.country_code == "TR") or (request.cookies.get("nexus_region") == "TR")
    has_steel = any(
        TaxService.is_steel_tevkifat_eligible(
            gtip_code=it.product.gtip_code if it.product else None,
            category_code=it.product.category.code if it.product and it.product.category else None,
            product_name=it.product.name if it.product else None
        ) for it in so.items
    )
    tax_info = TaxService.calculate_tax(
        base_amount=subtotal,
        region_code="TR" if is_tr else "IR",
        is_steel=has_steel,
        custom_vat_rate=so.vat_rate if so.vat_rate else None,
        tevkifat_ratio=so.tevkifat_rate
    )

    active_region = get_active_region(request)

    stock_map = {}
    for w in warehouses:
        stock_map[str(w.id)] = {}
        for it in so.items:
            avail = InventoryService.get_available_stock(db, it.product_id, w.id)
            cur = InventoryService.get_current_stock(db, it.product_id, w.id)
            stock_map[str(w.id)][str(it.product_id)] = {
                "available": round(avail, 3),
                "current": round(cur, 3)
            }

    user_role_names = [role.name for role in current_user.roles]
    is_admin = ("Admin" in user_role_names) or (current_user.username == "admin")
    is_finance = ("Finance_Manager" in user_role_names) or (current_user.username == "finance")

    # محاسبه بهای تمام‌شده موزون، سود ناخالص و حاشیه سود لحظه‌ای (مخصوص مدیر ارشد و مالی)
    item_profits = {}
    total_order_cost = 0.0
    total_order_profit = 0.0
    if is_admin or is_finance:
        for it in so.items:
            avg_cost = InventoryService.get_weighted_average_cost(db, it.product_id)
            unit_prof = it.unit_price - avg_cost
            line_cost = avg_cost * it.quantity
            line_prof = unit_prof * it.quantity
            margin_p = (unit_prof / it.unit_price * 100.0) if it.unit_price > 0 else 0.0
            total_order_cost += line_cost
            total_order_profit += line_prof
            item_profits[it.id] = {
                "avg_cost": avg_cost,
                "unit_profit": unit_prof,
                "line_cost": line_cost,
                "line_profit": line_prof,
                "margin_pct": round(margin_p, 1)
            }

    order_margin_pct = (total_order_profit / tax_info.base_amount * 100.0) if tax_info.base_amount > 0 else 0.0

    return templates.TemplateResponse(
        request=request,
        name="sales_detail.html",
        context={
            "request": request,
            "order": so,
            "warehouses": warehouses,
            "stock_map": stock_map,
            "stock_map_json": json.dumps(stock_map),
            "total_amount": tax_info.total_payable,
            "tax_info": tax_info,
            "item_profits": item_profits,
            "total_order_cost": total_order_cost,
            "total_order_profit": total_order_profit,
            "order_margin_pct": round(order_margin_pct, 1),
            "is_admin": is_admin,
            "is_finance": is_finance,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("/{order_id}/deliver", response_class=HTMLResponse)
async def deliver_sales_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    warehouse_id: int = Form(...),
    item_id: list[int] = Form(...),
    deliver_qty: list[float] = Form(...)
):
    """
    ثبت درخواست حواله خروج انبار برای سفارش فروش (Outbound Cartable Dispatch)
    بررسی موجودی آزاد انبار و صدور سند OUT با وضعیت PENDING_APPROVAL جهت تایید نهایی انباردار.
    """
    so = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="سفارش فروش یافت نشد")

    # جلوگیری از ثبت مضاعف بین باسکول و حواله خروج سفارش:
    active_wb = db.query(WeighbridgeTicket).filter(
        WeighbridgeTicket.sales_order_id == so.id,
        WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING
    ).first()
    if active_wb:
        return RedirectResponse(
            url=f"/sales/{so.id}?error=" + quote(f"کامیون این سفارش در حال حاضر روی باسکول و در مرحله توزین اول است (قبض #{active_wb.ticket_number} - پلاک {active_wb.truck_plate}). پس از ثبت توزین دوم، سند خروج به صورت خودکار به کارتابل انبار ارسال می‌شود."),
            status_code=303
        )

    try:
        active_fy = InventoryService.get_active_fiscal_year(db)

        # بررسی سقف اعتبار مالی مشتری
        if so.customer and so.customer.credit_limit and so.customer.credit_limit > 0:
            if (so.total_amount or 0.0) > so.customer.credit_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"مبلغ کل سفارش ({so.total_amount:,.0f}) بیش از سقف اعتبار مالی مشتری ({so.customer.name}: {so.customer.credit_limit:,.0f}) است. تحویل کالا مجاز نمی‌باشد."
                )

        created_count = 0
        for it_id, d_qty in zip(item_id, deliver_qty):
            if d_qty > 0:
                item = db.query(SalesOrderItem).filter(SalesOrderItem.id == it_id).first()
                if item:
                    # ۱. بررسی سقف تحویل سفارش با احتساب اسناد معلق کارتابل خروج
                    pending_out_qty = (
                        db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0))
                        .filter(
                            StockTransaction.sales_order_id == so.id,
                            StockTransaction.sales_order_item_id == item.id,
                            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
                        )
                        .scalar()
                    )
                    remaining_order_qty = (item.quantity * 1.05) - item.delivered_quantity - pending_out_qty
                    if d_qty > (remaining_order_qty + 0.0001):
                        raise HTTPException(
                            status_code=400,
                            detail=f"مقدار تحویلی قلم {item.product.name} ({d_qty}) بیشتر از مانده سفارش به همراه ۵٪ تلورانس و اسناد معلق کارتابل (سقف باقی‌مانده: {max(0.0, round(remaining_order_qty, 3))}) است."
                        )

                    # ۲. بررسی موجودی آزاد و قابل تخصیص انبار
                    avail_stock = InventoryService.get_available_stock(db, item.product_id, warehouse_id)
                    if d_qty > avail_stock:
                        raise HTTPException(
                            status_code=400,
                            detail=f"موجودی آزاد کالای {item.product.name} در این انبار ({avail_stock}) کافی نیست (درخواستی: {d_qty})."
                        )

                    # ۳. استخراج بهای تمام‌شده میانگین موزون برای کاردکس ریالی
                    avg_cost = InventoryService.get_weighted_average_cost(db, item.product_id, warehouse_id)

                    # ۴. صدور سند حواله خروج موقت (PENDING_APPROVAL) با سال مالی فعال
                    tx = StockTransaction(
                        transaction_type=TransactionType.OUT,
                        transaction_source=TransactionSource.SALES.value,
                        product_id=item.product_id,
                        warehouse_id=warehouse_id,
                        quantity=d_qty,
                        unit_price=avg_cost or item.unit_price,
                        customer_id=so.customer_id,
                        sales_order_id=so.id,
                        sales_order_item_id=item.id,
                        reference_document=so.so_number,
                        status=DocumentStatus.PENDING_APPROVAL,
                        fiscal_year_id=active_fy.id if active_fy else None,
                        created_by_id=current_user.id
                    )
                    db.add(tx)
                    created_count += 1

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="SalesOrder",
            entity_id=str(so.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"صدور {created_count} قلم حواله خروج موقت برای سفارش فروش {so.so_number} و ارسال به کارتابل انبار"
        )

        return RedirectResponse(
            url=f"/sales/{so.id}?msg=" + quote("حواله خروج موقت صادر شد و جهت تایید نهایی انباردار به کارتابل انبار ارسال گردید."),
            status_code=303
        )
    except HTTPException as he:
        db.rollback()
        return RedirectResponse(
            url=f"/sales/{so.id}?error=" + quote(he.detail),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        return RedirectResponse(
            url=f"/sales/{so.id}?error=" + quote(f"خطا در صدور حواله خروج انبار: {str(e)}"),
            status_code=303
        )


@router.post("/{order_id}/close-short", response_class=HTMLResponse)
async def close_short_sales_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ختم دستی سفارش فروش (Close Short) هنگام تحویل جزئی"""
    if po_or_so := db.query(SalesOrder).filter(SalesOrder.id == order_id).first():
        if po_or_so.status not in (SalesOrderStatus.PARTIALLY_DELIVERED, SalesOrderStatus.CONFIRMED):
            return RedirectResponse(
                url=f"/sales/{order_id}?error=" + quote("تنها سفارش‌های در حال ارسال یا تایید شده قابل ختم دستی می‌باشند."),
                status_code=303
            )
        po_or_so.status = SalesOrderStatus.COMPLETED
        db.commit()

        AuditService.log(
            db, action="UPDATE", entity_name="SalesOrder",
            entity_id=str(po_or_so.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ختم دستی سفارش فروش {po_or_so.so_number} با وضعیت تکمیل نهایی (Close Short)"
        )

        return RedirectResponse(
            url=f"/sales/{order_id}?msg=" + quote("سفارش فروش به صورت دستی ختم شد و وضعیت آن تکمیل نهایی ثبت گردید."),
            status_code=303
        )
    raise HTTPException(status_code=404, detail="سفارش فروش یافت نشد")

