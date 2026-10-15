import os
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
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    Product,
    Warehouse,
    StockTransaction,
    TransactionType,
    WeighbridgeTicket
)
from src.domain_model.enums import PurchaseOrderStatus, DocumentStatus, TransactionSource, WeighbridgeStatus
from src.services.audit_service import AuditService
from src.services.tax_service import TaxService
from src.services.inventory_service import InventoryService
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(
    prefix="/purchases",
    tags=["Purchase Orders"],
    dependencies=[Depends(allow_roles("Admin", "Commercial_Officer", "Finance_Manager", "Warehouse_Supervisor"))]
)
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name



@router.get("", response_class=HTMLResponse)
async def list_purchase_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None),
    supplier_filter: Optional[int] = Query(None)
):
    """لیست و داشبورد سفارشات خرید کالا از کارخانجات و تأمین‌کنندگان"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    query = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.created_by),
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product)
        )
        .order_by(PurchaseOrder.created_at.desc())
    )

    if status_filter:
        query = query.filter(PurchaseOrder.status == PurchaseOrderStatus[status_filter])
    if supplier_filter:
        query = query.filter(PurchaseOrder.supplier_id == supplier_filter)

    orders = query.all()
    suppliers = db.query(Supplier).filter_by(is_active=True).order_by(Supplier.name).all()

    # محاسبات آماری و کارت‌های KPI
    total_orders = len(orders)
    pending_receipt = sum(1 for o in orders if o.status in (PurchaseOrderStatus.CONFIRMED, PurchaseOrderStatus.PARTIALLY_RECEIVED))
    completed_orders = sum(1 for o in orders if o.status == PurchaseOrderStatus.COMPLETED)
    
    total_value = 0.0
    for o in orders:
        for item in o.items:
            total_value += (item.total_price or (item.quantity * item.unit_price))

    return templates.TemplateResponse(
        request=request,
        name="purchases.html",
        context={
            "request": request,
            "orders": orders,
            "suppliers": suppliers,
            "status_filter": status_filter,
            "supplier_filter": supplier_filter,
            "total_orders": total_orders,
            "pending_receipt": pending_receipt,
            "completed_orders": completed_orders,
            "total_value": total_value,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_purchase_order_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت سفارش خرید جدید (PO)"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    suppliers = db.query(Supplier).filter_by(is_active=True).order_by(Supplier.name).all()
    products = db.query(Product).filter_by(is_active=True).order_by(Product.name).all()

    # تولید شماره سفارش بعدی
    count = db.query(PurchaseOrder).count() + 1
    generated_po_number = f"PO-TR-{count:04d}" if is_tr else f"PO-1403-{count:04d}"

    return templates.TemplateResponse(
        request=request,
        name="purchase_form.html",
        context={
            "request": request,
            "suppliers": suppliers,
            "products": products,
            "generated_po_number": generated_po_number,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_purchase_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    po_number: str = Form(...),
    supplier_id: int = Form(...),
    delivery_due_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    product_id: list[int] = Form(...),
    quantity: list[float] = Form(...),
    unit_price: list[float] = Form(...)
):
    """ذخیره سفارش خرید و اقلام مربوطه با محاسبه خودکار مالیات و توقیف آهن‌آلات"""
    try:
        # تشخیص منطقه جغرافیایی سفارش منحصراً از روی کشور تأمین‌کننده (حذف وابستگی به کوکی مرورگر)
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        is_tr = bool(supplier and supplier.country_code == "TR")
        region_code = "TR" if is_tr else "IR"

        # بررسی اقلام، محاسبه مبلغ خالص پایه و بررسی مشمولیت توقیف آهن و فولاد
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

        # اجرای موتور محاسبه مالیات و توقیف آهن‌آلات (فقط روی اقلام فولادی)
        tax_res = TaxService.calculate_tax(
            base_amount=subtotal,
            region_code=region_code,
            is_steel=has_steel,
            steel_base_amount=steel_subtotal
        )

        po = PurchaseOrder(
            po_number=po_number.strip(),
            supplier_id=supplier_id,
            delivery_due_date=delivery_due_date.strip() if delivery_due_date else None,
            status=PurchaseOrderStatus.CONFIRMED,
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
        db.add(po)
        db.flush()

        for pid, qty, price, line_total in valid_items_data:
            item = PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=pid,
                quantity=qty,
                received_quantity=0.0,
                unit_price=price,
                total_price=line_total
            )
            db.add(item)

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="PurchaseOrder",
            entity_id=str(po.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت سفارش خرید {po.po_number} (پایه: {tax_res.base_amount} {tax_res.currency_symbol} - توقیف: {tax_res.tevkifat_amount} - نهایی: {tax_res.total_payable})"
        )


        return RedirectResponse(
            url=f"/purchases/{po.id}?msg=" + quote(f"سفارش خرید {po.po_number} با موفقیت ثبت گردید"),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        suppliers = db.query(Supplier).filter_by(is_active=True).all()
        products = db.query(Product).filter_by(is_active=True).all()
        return templates.TemplateResponse(
            request=request,
            name="purchase_form.html",
            context={
                "request": request,
                "suppliers": suppliers,
                "products": products,
                "error": f"خطا در ثبت سفارش خرید: {str(e)}",
                "generated_po_number": po_number,
                "user": current_user
            },
            status_code=400
        )


@router.get("/{order_id}", response_class=HTMLResponse)
async def view_purchase_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مشاهده جزئیات سفارش خرید و وضعیت دریافت اقلام با گزارش تفصیلی مالیاتی"""
    po = (
        db.query(PurchaseOrder)
        .options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.created_by),
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.product)
        )
        .filter(PurchaseOrder.id == order_id)
        .first()
    )
    if not po:
        raise HTTPException(status_code=404, detail="سفارش خرید مورد نظر یافت نشد")

    warehouses = db.query(Warehouse).all()

    # محاسبه مجدد مشخصات مالیاتی در صورت نیاز
    subtotal = po.subtotal_amount or sum(item.total_price for item in po.items)
    is_tr = (po.currency == "TRY") or (po.supplier and po.supplier.country_code == "TR") or (request.cookies.get("nexus_region") == "TR")
    has_steel = any(
        TaxService.is_steel_tevkifat_eligible(
            gtip_code=it.product.gtip_code if it.product else None,
            category_code=it.product.category.code if it.product and it.product.category else None,
            product_name=it.product.name if it.product else None
        ) for it in po.items
    )
    tax_info = TaxService.calculate_tax(
        base_amount=subtotal,
        region_code="TR" if is_tr else "IR",
        is_steel=has_steel,
        custom_vat_rate=po.vat_rate if po.vat_rate else None,
        tevkifat_ratio=po.tevkifat_rate
    )

    active_region = get_active_region(request)

    return templates.TemplateResponse(
        request=request,
        name="purchase_detail.html",
        context={
            "request": request,
            "order": po,
            "warehouses": warehouses,
            "total_amount": tax_info.total_payable,
            "tax_info": tax_info,
            "is_tr": is_tr,
            "user": current_user,
            "active_region": active_region
        }
    )


@router.post("/{order_id}/receive", response_class=HTMLResponse)
async def receive_purchase_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    warehouse_id: int = Form(...),
    item_id: list[int] = Form(...),
    receive_qty: list[float] = Form(...)
):
    """
    ثبت درخواست رسید انبار برای سفارش خرید (Inbound Cartable Dispatch)
    ایجاد سند ورودی در وضعیت PENDING_APPROVAL جهت بررسی و تایید نهایی انباردار در کارتابل.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="سفارش خرید یافت نشد")

    # جلوگیری از ثبت مضاعف بین باسکول و دریافت سفارش:
    active_wb = db.query(WeighbridgeTicket).filter(
        WeighbridgeTicket.purchase_order_id == po.id,
        WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING
    ).first()
    if active_wb:
        raise HTTPException(
            status_code=400,
            detail=f"کامیون این سفارش در حال حاضر روی باسکول و در مرحله توزین اول است (قبض #{active_wb.ticket_number} - پلاک {active_wb.truck_plate}). پس از ثبت توزین دوم، سند به صورت خودکار به کارتابل انبار ارسال می‌شود."
        )

    try:
        active_fy = InventoryService.get_active_fiscal_year(db)
        created_receipts = 0
        for it_id, r_qty in zip(item_id, receive_qty):
            if r_qty > 0:
                item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == it_id).first()
                if item:
                    # محاسبه اسناد در انتظار تایید کارتابل برای این ردیف سفارش (جهت کنترل سقف تلورانس)
                    pending_in_qty = (
                        db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0))
                        .filter(
                            StockTransaction.purchase_order_id == po.id,
                            StockTransaction.purchase_order_item_id == item.id,
                            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
                        )
                        .scalar()
                    )
                    # کنترل سقف ۵٪ تلورانس باسکول با لحاظ اسناد معلق کارتابل
                    max_allowed_receive = (item.quantity * 1.05) - item.received_quantity - pending_in_qty
                    if r_qty > (max_allowed_receive + 0.0001):
                        raise HTTPException(
                            status_code=400,
                            detail=f"مقدار دریافتی برای قلم {item.product.name} ({r_qty}) بیش از سقف مجاز سفارش به همراه ۵٪ تلورانس باسکول و اسناد معلق کارتابل (سقف باقی‌مانده: {max(0.0, round(max_allowed_receive, 3))}) است."
                        )

                    # صدور سند رسید موقت انبار در کارتابل (PENDING_APPROVAL)
                    tx = StockTransaction(
                        transaction_type=TransactionType.IN,
                        transaction_source=TransactionSource.PURCHASE.value,
                        product_id=item.product_id,
                        warehouse_id=warehouse_id,
                        quantity=r_qty,
                        unit_price=item.unit_price,
                        supplier_id=po.supplier_id,
                        purchase_order_id=po.id,
                        purchase_order_item_id=item.id,
                        reference_document=po.po_number,
                        status=DocumentStatus.PENDING_APPROVAL,
                        fiscal_year_id=active_fy.id if active_fy else None,
                        created_by_id=current_user.id
                    )
                    db.add(tx)
                    created_receipts += 1

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="PurchaseOrder",
            entity_id=str(po.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"صدور {created_receipts} قلم رسید موقت برای سفارش خرید {po.po_number} و ارسال به کارتابل انبار"
        )

        return RedirectResponse(
            url=f"/purchases/{po.id}?msg=" + quote(f"رسید موقت انبار صادر شد و جهت تایید نهایی و اعمال در موجودی به کارتابل انبار ارسال گردید."),
            status_code=303
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در صدور رسید انبار: {str(e)}")


@router.post("/{order_id}/close-short", response_class=HTMLResponse)
async def close_short_purchase_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ختم دستی سفارش خرید (Close Short) هنگام تحویل جزئی"""
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="سفارش خرید یافت نشد")

    if po.status not in (PurchaseOrderStatus.PARTIALLY_RECEIVED, PurchaseOrderStatus.CONFIRMED):
        raise HTTPException(status_code=400, detail="تنها سفارش‌های در حال تحویل یا تایید شده قابل ختم دستی می‌باشند.")

    po.status = PurchaseOrderStatus.COMPLETED
    db.commit()

    AuditService.log(
        db, action="UPDATE", entity_name="PurchaseOrder",
        entity_id=str(po.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"ختم دستی سفارش خرید {po.po_number} با وضعیت تکمیل نهایی (Close Short)"
    )

    return RedirectResponse(
        url=f"/purchases/{po.id}?msg=" + quote("سفارش خرید به صورت دستی ختم شد و وضعیت آن تکمیل نهایی ثبت گردید."),
        status_code=303
    )

