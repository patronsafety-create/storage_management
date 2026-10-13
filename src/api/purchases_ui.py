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
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import (
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    Product,
    Warehouse,
    StockTransaction,
    TransactionType
)
from src.domain_model.enums import PurchaseOrderStatus, DocumentStatus
from src.services.audit_service import AuditService

router = APIRouter(prefix="/purchases", tags=["Purchase Orders"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def list_purchase_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None),
    supplier_filter: Optional[int] = Query(None)
):
    """لیست و داشبورد سفارشات خرید کالا از کارخانجات و تأمین‌کنندگان"""
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
            "user": current_user
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_purchase_order_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت سفارش خرید جدید (PO)"""
    suppliers = db.query(Supplier).filter_by(is_active=True).order_by(Supplier.name).all()
    products = db.query(Product).filter_by(is_active=True).order_by(Product.name).all()

    # تولید شماره سفارش بعدی
    count = db.query(PurchaseOrder).count() + 1
    generated_po_number = f"PO-1403-{count:04d}"

    return templates.TemplateResponse(
        request=request,
        name="purchase_form.html",
        context={
            "request": request,
            "suppliers": suppliers,
            "products": products,
            "generated_po_number": generated_po_number,
            "user": current_user
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
    """ذخیره سفارش خرید و اقلام مربوطه"""
    try:
        po = PurchaseOrder(
            po_number=po_number.strip(),
            supplier_id=supplier_id,
            delivery_due_date=delivery_due_date.strip() if delivery_due_date else None,
            status=PurchaseOrderStatus.CONFIRMED,
            notes=notes.strip() if notes else None,
            created_by_id=current_user.id
        )
        db.add(po)
        db.flush()

        for pid, qty, price in zip(product_id, quantity, unit_price):
            if qty > 0:
                item = PurchaseOrderItem(
                    purchase_order_id=po.id,
                    product_id=pid,
                    quantity=qty,
                    received_quantity=0.0,
                    unit_price=price,
                    total_price=qty * price
                )
                db.add(item)

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="PurchaseOrder",
            entity_id=str(po.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت سفارش خرید {po.po_number} برای تأمین‌کننده کد {supplier_id}"
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
    """مشاهده جزئیات سفارش خرید و وضعیت دریافت اقلام"""
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

    # کل مبلغ سفارش
    total_amount = sum(item.total_price for item in po.items)

    return templates.TemplateResponse(
        request=request,
        name="purchase_detail.html",
        context={
            "request": request,
            "order": po,
            "warehouses": warehouses,
            "total_amount": total_amount,
            "user": current_user
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
    تبدیل مستقیم سفارش خرید به رسید انبار (Inbound Receipt Matching)
    با کسر از باقیمانده سفارش و ثبت تراکنش رسمی ورود به انبار.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="سفارش خرید یافت نشد")

    try:
        total_remaining_after = 0.0

        for it_id, r_qty in zip(item_id, receive_qty):
            if r_qty > 0:
                item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == it_id).first()
                if item:
                    item.received_quantity += r_qty
                    rem = item.quantity - item.received_quantity
                    if rem > 0:
                        total_remaining_after += rem

                    # صدور سند رسید انبار (StockTransaction IN)
                    tx = StockTransaction(
                        transaction_type=TransactionType.IN,
                        product_id=item.product_id,
                        warehouse_id=warehouse_id,
                        quantity=r_qty,
                        unit_price=item.unit_price,
                        supplier_id=po.supplier_id,
                        reference_document=po.po_number,
                        status=DocumentStatus.APPROVED,
                        created_by_id=current_user.id
                    )
                    db.add(tx)

        if total_remaining_after <= 0.001:
            po.status = PurchaseOrderStatus.COMPLETED
        else:
            po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED

        db.commit()

        AuditService.log(
            db, action="APPROVE", entity_name="PurchaseOrder",
            entity_id=str(po.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"تخلیه و صدور رسید انبار برای سفارش خرید {po.po_number}"
        )

        return RedirectResponse(
            url=f"/purchases/{po.id}?msg=" + quote(f"رسید انبار برای سفارش {po.po_number} صادر و موجودی افزایش یافت"),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در صدور رسید انبار: {str(e)}")
