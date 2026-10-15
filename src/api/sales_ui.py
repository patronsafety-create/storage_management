from typing import Optional
from urllib.parse import quote
from datetime import datetime

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
    TransactionType
)
from src.domain_model.enums import SalesOrderStatus, DocumentStatus, TransactionSource
from src.services.audit_service import AuditService
from src.services.tax_service import TaxService
from src.services.inventory_service import InventoryService
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(
    prefix="/sales",
    tags=["Sales Orders"],
    dependencies=[Depends(allow_roles("Admin", "Commercial_Officer", "Finance_Manager", "Warehouse_Supervisor"))]
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

    return templates.TemplateResponse(
        request=request,
        name="sales_form.html",
        context={
            "request": request,
            "customers": customers,
            "products": products,
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
    notes: Optional[str] = Form(None),
    product_id: list[int] = Form(...),
    quantity: list[float] = Form(...),
    unit_price: list[float] = Form(...)
):
    """ثبت و ذخیره سفارش فروش با تفکیک توقیف مالیاتی آهن‌آلات"""
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

        so = SalesOrder(
            so_number=so_number.strip(),
            customer_id=customer_id,
            delivery_due_date=delivery_due_date.strip() if delivery_due_date else None,
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
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    return templates.TemplateResponse(
        request=request,
        name="sales_detail.html",
        context={
            "request": request,
            "order": so,
            "warehouses": warehouses,
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
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در صدور حواله خروج انبار: {str(e)}")


@router.post("/{order_id}/close-short", response_class=HTMLResponse)
async def close_short_sales_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ختم دستی سفارش فروش (Close Short) هنگام تحویل جزئی"""
    so = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="سفارش فروش یافت نشد")

    if so.status not in (SalesOrderStatus.PARTIALLY_DELIVERED, SalesOrderStatus.CONFIRMED):
        raise HTTPException(status_code=400, detail="تنها سفارش‌های در حال ارسال یا تایید شده قابل ختم دستی می‌باشند.")

    so.status = SalesOrderStatus.COMPLETED
    db.commit()

    AuditService.log(
        db, action="UPDATE", entity_name="SalesOrder",
        entity_id=str(so.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"ختم دستی سفارش فروش {so.so_number} با وضعیت تکمیل نهایی (Close Short)"
    )

    return RedirectResponse(
        url=f"/sales/{so.id}?msg=" + quote("سفارش فروش به صورت دستی ختم شد و وضعیت آن تکمیل نهایی ثبت گردید."),
        status_code=303
    )

