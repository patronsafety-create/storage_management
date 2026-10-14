import csv
import io
from urllib.parse import quote
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from src.core.dependencies import get_db, get_current_user
from src.services.inventory_service import InventoryService
from src.services.audit_service import AuditService
from src.domain_model.inventory_models import (
    Product, Warehouse, StockTransaction, TransactionType, Supplier, Customer,
    FiscalYear, PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem, WeighbridgeTicket
)
from src.domain_model.auth_models import User
from src.domain_model.enums import (
    DocumentStatus, PurchaseOrderStatus, SalesOrderStatus, TransactionSource, WeighbridgeStatus
)
from src.core.localization.regions import localize_display_name, get_active_region, register_jinja_filters, format_date_localized
from src.infrastructure.number_normalizer import parse_float_safe, normalize_number_str

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory UI"],
    dependencies=[Depends(get_current_user)]
)
templates = Jinja2Templates(directory="templates")
register_jinja_filters(templates)

ITEMS_PER_PAGE = 10


def require_roles(user: User, allowed_roles: set[str], action_desc: str = ""):
    """
    قفل امنیتی دسترسی در سمت سرور (Backend RBAC Guard):
    در صورت عدم احراز نقش، خطای HTTP 403 با پیام عدم دسترسی به این عملیات صادر می‌شود.
    """
    user_roles = {r.name for r in getattr(user, "roles", [])}
    if not user_roles.intersection(allowed_roles):
        raise HTTPException(
            status_code=403,
            detail="عدم دسترسی به این عملیات / Bu işlem için yetkiniz bulunmamaktadır"
        )


# ==========================================
# ۱. فرم ثبت رسید و حواله
# ==========================================
@router.get("/transaction", response_class=HTMLResponse)
async def get_transaction_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    suppliers = db.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name).all()
    customers = db.query(Customer).filter(Customer.is_active == True).order_by(Customer.name).all()
    purchase_orders = db.query(PurchaseOrder).filter(PurchaseOrder.status.in_([PurchaseOrderStatus.CONFIRMED, PurchaseOrderStatus.PARTIALLY_RECEIVED])).all()
    sales_orders = db.query(SalesOrder).filter(SalesOrder.status.in_([SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED])).all()

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="transaction_form.html",
        context={
            "request": request,
            "products": products,
            "warehouses": warehouses,
            "suppliers": suppliers,
            "customers": customers,
            "purchase_orders": purchase_orders,
            "sales_orders": sales_orders,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.post("/transaction")
async def process_transaction(
    request: Request,
    transaction_type: str = Form(...),
    product_id: int = Form(...),
    warehouse_id: int = Form(...),
    quantity: float = Form(...),
    unit_price: Optional[float] = Form(0.0),
    supplier_id: Optional[int] = Form(None),
    customer_id: Optional[int] = Form(None),
    batch_number: Optional[str] = Form(None),
    reference_document: Optional[str] = Form(None),
    doc_status: Optional[str] = Form("APPROVED"),
    # منبع تراکنش و سفارشات مرتبط
    transaction_source: Optional[str] = Form(None),
    purchase_order_id: Optional[int] = Form(None),
    purchase_order_item_id: Optional[int] = Form(None),
    sales_order_id: Optional[int] = Form(None),
    sales_order_item_id: Optional[int] = Form(None),
    # ۲. موتور دو واحدی
    secondary_quantity: Optional[float] = Form(None),
    secondary_uom: Optional[str] = Form(None),
    # ۶. بهای تمام شده و لجستیک
    freight_cost: Optional[float] = Form(0.0),
    insurance_cost: Optional[float] = Form(0.0),
    weighbridge_cost: Optional[float] = Form(0.0),
    bill_of_lading_qty: Optional[float] = Form(None),
    allowed_tolerance_percent: Optional[float] = Form(0.3),
    # ۹. شجره‌نامه ذوب و متالورژی
    heat_number: Optional[str] = Form(None),
    mtc_number: Optional[str] = Form(None),
    chemical_analysis: Optional[str] = Form(None),
    mechanical_analysis: Optional[str] = Form(None),
    # ۱۲. سامانه تجارت
    waybill_number: Optional[str] = Form(None),
    tracking_code: Optional[str] = Form(None),
    currency: Optional[str] = Form(None),
    exchange_rate: Optional[float] = Form(1.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    def error_response(msg: str):
        return templates.TemplateResponse(
            request=request,
            name="transaction_form.html",
            context={
                "request": request,
                "products": db.query(Product).filter(Product.is_active == True).order_by(Product.name).all(),
                "warehouses": db.query(Warehouse).order_by(Warehouse.name).all(),
                "suppliers": db.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name).all(),
                "customers": db.query(Customer).filter(Customer.is_active == True).order_by(Customer.name).all(),
                "purchase_orders": db.query(PurchaseOrder).filter(PurchaseOrder.status.in_([PurchaseOrderStatus.CONFIRMED, PurchaseOrderStatus.PARTIALLY_RECEIVED])).all(),
                "sales_orders": db.query(SalesOrder).filter(SalesOrder.status.in_([SalesOrderStatus.CONFIRMED, SalesOrderStatus.PARTIALLY_DELIVERED])).all(),
                "error": msg,
                "user": current_user
            },
            status_code=400
        )

    try:
        tx_enum = TransactionType.IN if transaction_type == "IN" else TransactionType.OUT
        src_val = (transaction_source or "").strip()

        # قفل هوشمند فرم دستی: ثبت مستقیم بدون شماره سفارش فقط برای موجودی اول دوره یا مصرف داخلی
        if tx_enum == TransactionType.IN:
            if not purchase_order_id and src_val not in (TransactionSource.OPENING_BALANCE.value, TransactionSource.INTERNAL_USE.value, TransactionSource.IN_ADJUSTMENT.value, TransactionSource.TRANSFER.value, TransactionSource.RETURN.value):
                return error_response("ثبت مستقیم ورود کالا بدون سفارش خرید (PO) فقط برای «موجودی اول دوره» یا «مصرف داخلی» مجاز است. لطفاً سفارش خرید مربوطه را مشخص کنید.")
        elif tx_enum == TransactionType.OUT:
            if not sales_order_id and src_val not in (TransactionSource.INTERNAL_USE.value, TransactionSource.OUT_ADJUSTMENT.value, TransactionSource.TRANSFER.value, TransactionSource.RETURN.value):
                return error_response("ثبت مستقیم خروج کالا بدون سفارش فروش (SO) مجاز نمی‌باشد (مگر برای مصرف داخلی).")

        # فاز ۵ باگ ۷: کنترل موجودی رزرو شده (Available Stock)
        if tx_enum == TransactionType.OUT:
            available_stock = InventoryService.get_available_stock(db, product_id, warehouse_id)
            if quantity > available_stock:
                return error_response(
                    f"موجودی آزاد و قابل تحویل کالا کافی نیست! موجودی آزاد با احتساب رزروهای کارتابل: {available_stock:.2f}، مقدار درخواستی: {quantity:.2f}"
                )

        # فاز ۵ باگ ۳: نرخ‌گذاری خودکار خروجی‌ها با آخرین فی میانگین موزون
        if tx_enum == TransactionType.OUT and (not unit_price or unit_price <= 0):
            unit_price = InventoryService.get_weighted_average_cost(db, product_id, warehouse_id)

        # محاسبات دو واحدی دینامیک
        weight_per_unit = (quantity / secondary_quantity) if (secondary_quantity and secondary_quantity > 0) else None
        prod = db.query(Product).filter(Product.id == product_id).first()
        std_w = prod.nominal_weight if (prod and prod.nominal_weight) else None
        deviation_pct = None
        if weight_per_unit and std_w and std_w > 0:
            deviation_pct = round(((weight_per_unit - std_w) / std_w) * 100.0, 2)

        # فرمول جریمه افت بار فقط روی مازاد افت مجاز (۰.۳٪ پیش‌فرض)
        tol_pct = allowed_tolerance_percent if (allowed_tolerance_percent is not None and allowed_tolerance_percent >= 0) else 0.3
        shrink_qty = max(0.0, bill_of_lading_qty - quantity) if (bill_of_lading_qty and bill_of_lading_qty > quantity) else 0.0
        shrink_pct = (shrink_qty / bill_of_lading_qty * 100.0) if (bill_of_lading_qty and bill_of_lading_qty > 0) else None
        allowed_qty = (bill_of_lading_qty * (tol_pct / 100.0)) if bill_of_lading_qty else 0.0
        excess_shrink_qty = max(0.0, shrink_qty - allowed_qty)
        penalty = excess_shrink_qty * (unit_price or 0.0)
        net_freight = max(0.0, (freight_cost or 0.0) - penalty)
        total_landed = (quantity * (unit_price or 0.0)) + net_freight + (insurance_cost or 0.0) + (weighbridge_cost or 0.0)
        effective_unit_cost = (total_landed / quantity) if quantity > 0 else (unit_price or 0.0)
        if tx_enum == TransactionType.IN and effective_unit_cost > 0:
            unit_price = effective_unit_cost

        # سال مالی فعال
        active_fy = InventoryService.get_active_fiscal_year(db)
        fiscal_year_id = active_fy.id if active_fy else None

        # منبع تراکنش پیش‌فرض در صورت خالی بودن
        if not src_val:
            if tx_enum == TransactionType.IN:
                src_val = TransactionSource.PURCHASE.value if purchase_order_id else TransactionSource.INTERNAL_USE.value
            else:
                src_val = TransactionSource.SALES.value if sales_order_id else TransactionSource.INTERNAL_USE.value

        # وضعیت سند
        status_enum = DocumentStatus[doc_status] if (doc_status and doc_status in DocumentStatus.__members__) else DocumentStatus.APPROVED

        wh_target = db.query(Warehouse).get(warehouse_id)
        tx_currency = currency or (wh_target.currency if wh_target and wh_target.currency else "IRR")
        tx_exchange_rate = exchange_rate if (exchange_rate and exchange_rate > 0) else 1.0

        new_transaction = StockTransaction(
            transaction_type=tx_enum,
            transaction_source=src_val,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            unit_price=unit_price or 0.0,
            currency=tx_currency,
            exchange_rate=tx_exchange_rate,
            supplier_id=supplier_id if tx_enum == TransactionType.IN and supplier_id and supplier_id > 0 else None,
            customer_id=customer_id if tx_enum == TransactionType.OUT and customer_id and customer_id > 0 else None,
            purchase_order_id=purchase_order_id if purchase_order_id and purchase_order_id > 0 else None,
            purchase_order_item_id=purchase_order_item_id if purchase_order_item_id and purchase_order_item_id > 0 else None,
            sales_order_id=sales_order_id if sales_order_id and sales_order_id > 0 else None,
            sales_order_item_id=sales_order_item_id if sales_order_item_id and sales_order_item_id > 0 else None,
            fiscal_year_id=fiscal_year_id,
            transaction_date=datetime.now(timezone.utc),
            batch_number=batch_number or None,
            reference_document=reference_document or None,
            status=status_enum,
            # دو واحدی
            secondary_quantity=secondary_quantity,
            secondary_uom=secondary_uom or (prod.secondary_uom if prod else None),
            weight_per_unit=weight_per_unit,
            standard_weight=std_w,
            deviation_percent=deviation_pct,
            # لجستیک و تلورانس
            freight_cost=freight_cost or 0.0,
            insurance_cost=insurance_cost or 0.0,
            weighbridge_cost=weighbridge_cost or 0.0,
            bill_of_lading_qty=bill_of_lading_qty,
            shrinkage_qty=shrink_qty,
            shrinkage_percent=round(shrink_pct, 2) if shrink_pct else None,
            allowed_tolerance_percent=tol_pct,
            penalty_amount=penalty,
            total_landed_cost=total_landed,
            # متالورژی و ذوب
            heat_number=heat_number or None,
            mtc_number=mtc_number or None,
            chemical_analysis=chemical_analysis or None,
            mechanical_analysis=mechanical_analysis or None,
            # سامانه جامع تجارت
            waybill_number=waybill_number or None,
            tracking_code=tracking_code or None,
            created_by_id=current_user.id
        )
        db.add(new_transaction)
        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="StockTransaction",
            entity_id=str(new_transaction.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت سند {tx_enum.value} به مقدار {quantity} {prod.uom if prod else ''} در انبار {new_transaction.warehouse_id} (منبع: {src_val})"
        )

        return RedirectResponse(url="/dashboard?msg=" + quote("تراکنش انبار با موفقیت ثبت شد"), status_code=303)

    except IntegrityError:
        db.rollback()
        return error_response("خطای یکپارچگی داده: مقدار یا نوع تراکنش نامعتبر است.")
    except Exception as e:
        db.rollback()
        return error_response(f"خطای سیستمی در ثبت تراکنش: {str(e)}")



# ==========================================
# ۲. گزارش موجودی لحظه‌ای
# ==========================================
@router.get("/balance", response_class=HTMLResponse)
async def get_stock_balance(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stock_balances = InventoryService.calculate_stock_balances(db)
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="stock_balance.html",
        context={
            "request": request,
            "stock_balances": stock_balances,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


# ==========================================
# ۳. لیست و تاریخچه تراکنش‌ها
# ==========================================
@router.get("/transactions", response_class=HTMLResponse)
async def list_transactions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tx_type: Optional[str] = Query(None),
    product_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1)
):
    query = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer),
            joinedload(StockTransaction.created_by)
        )
        .order_by(StockTransaction.created_at.desc())
    )

    if tx_type in ("IN", "OUT"):
        query = query.filter(StockTransaction.transaction_type == TransactionType[tx_type])
    if product_id:
        query = query.filter(StockTransaction.product_id == product_id)

    total = query.count()
    total_pages = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = min(page, total_pages)
    transactions = query.offset((page - 1) * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE).all()

    products = db.query(Product).order_by(Product.name).all()
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="transactions.html",
        context={
            "request": request,
            "transactions": transactions,
            "products": products,
            "user": current_user,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "filter_type": tx_type,
            "filter_product": product_id,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


# ==========================================
# ۴. کاردکس مقداری کالا
# ==========================================
@router.get("/kardex/{product_id}", response_class=HTMLResponse)
async def kardex(
    request: Request,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    warehouse_id: Optional[int] = Query(None)
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse(url="/inventory/balance", status_code=303)

    query = (
        db.query(StockTransaction)
        .filter(StockTransaction.product_id == product_id)
        .order_by(StockTransaction.created_at.asc())
    )
    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    raw_transactions = query.all()
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    all_products = db.query(Product).order_by(Product.name).all()

    running_balance = 0.0
    kardex_entries = []
    for tx in raw_transactions:
        if tx.transaction_type == TransactionType.IN:
            running_balance += tx.quantity
        else:
            running_balance -= tx.quantity
        kardex_entries.append({"tx": tx, "running_balance": round(running_balance, 3)})

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="kardex.html",
        context={
            "request": request,
            "product": product,
            "kardex_entries": kardex_entries,
            "warehouses": warehouses,
            "all_products": all_products,
            "selected_warehouse_id": warehouse_id,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


# ==========================================
# ۵. انتقال بین انبارها (Inter-Warehouse Transfer)
# ==========================================
@router.get("/transfer", response_class=HTMLResponse)
async def get_transfer_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    products = db.query(Product).order_by(Product.name).all()
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="transfer_form.html",
        context={
            "request": request,
            "products": products,
            "warehouses": warehouses,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.post("/transfer")
async def process_transfer(
    request: Request,
    product_id: int = Form(...),
    from_warehouse_id: int = Form(...),
    to_warehouse_id: int = Form(...),
    quantity: float = Form(...),
    secondary_quantity: Optional[float] = Form(None),
    reference_document: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    def error_response(msg: str):
        return templates.TemplateResponse(
            request=request,
            name="transfer_form.html",
            context={
                "request": request,
                "products": db.query(Product).order_by(Product.name).all(),
                "warehouses": db.query(Warehouse).order_by(Warehouse.name).all(),
                "error": msg,
                "user": current_user,
                "active_region": active_region,
                "is_tr": is_tr,
            },
            status_code=400
        )

    if from_warehouse_id == to_warehouse_id:
        return error_response("انبار مبدأ و مقصد نمی‌توانند یکسان باشند.")

    current_stock = InventoryService.get_current_stock(db, product_id, from_warehouse_id)
    if quantity > current_stock:
        return error_response(f"موجودی انبار مبدأ کافی نیست (موجودی فعلی: {current_stock}، درخواستی: {quantity}).")

    from_wh = db.query(Warehouse).filter_by(id=from_warehouse_id).first()
    to_wh = db.query(Warehouse).filter_by(id=to_warehouse_id).first()
    prod = db.query(Product).filter_by(id=product_id).first()
    ref = reference_document or f"TRF-{from_warehouse_id}-to-{to_warehouse_id}"

    # تعیین خودکار فی میانگین موزون برای اسناد انتقال
    avg_cost = InventoryService.get_weighted_average_cost(db, product_id, from_warehouse_id)
    active_fy = InventoryService.get_active_fiscal_year(db)
    fy_id = active_fy.id if active_fy else None

    from_currency = from_wh.currency or "IRR"

    # خروج از مبدأ (قطعی و با فی میانگین موزون مبدأ)
    tx_out = StockTransaction(
        transaction_type=TransactionType.OUT,
        transaction_source=TransactionSource.TRANSFER.value,
        product_id=product_id,
        warehouse_id=from_warehouse_id,
        quantity=quantity,
        secondary_quantity=secondary_quantity,
        secondary_uom=prod.secondary_uom if prod else None,
        unit_price=avg_cost,
        currency=from_currency,
        exchange_rate=1.0,
        status=DocumentStatus.APPROVED,
        fiscal_year_id=fy_id,
        reference_document=f"{ref} (انتقال به {to_wh.name})",
        created_by_id=current_user.id,
        approved_by_id=current_user.id,
        approved_at=datetime.now(timezone.utc)
    )
    # ورود به مقصد (کالای در راه - در انتظار تایید انباردار مقصد در کارتابل)
    tx_in = StockTransaction(
        transaction_type=TransactionType.IN,
        transaction_source=TransactionSource.TRANSFER.value,
        product_id=product_id,
        warehouse_id=to_warehouse_id,
        quantity=quantity,
        secondary_quantity=secondary_quantity,
        secondary_uom=prod.secondary_uom if prod else None,
        unit_price=avg_cost,
        currency=from_currency,
        exchange_rate=1.0,
        status=DocumentStatus.PENDING_APPROVAL,
        fiscal_year_id=fy_id,
        reference_document=f"{ref} (انتقال از {from_wh.name} - در انتظار وصول)",
        created_by_id=current_user.id
    )
    db.add_all([tx_out, tx_in])
    db.commit()
    return RedirectResponse(url="/inventory/transactions?msg=" + quote("حواله خروج انتقال صادر شد و سند ورود جهت وصول به کارتابل انبار مقصد ارسال گردید"), status_code=303)


# ==========================================
# ۶. انبارگردانی و مغایرت‌گیری (Stocktaking)
# ==========================================
@router.get("/stocktaking", response_class=HTMLResponse)
async def get_stocktaking_form(
    request: Request,
    warehouse_id: Optional[int] = Query(None),
    msg: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    selected_warehouse = db.query(Warehouse).filter_by(id=warehouse_id).first() if warehouse_id else None
    items = []
    if selected_warehouse:
        products = db.query(Product).order_by(Product.name).all()
        for p in products:
            sys_stock = InventoryService.get_current_stock(db, p.id, selected_warehouse.id)
            sys_sec = InventoryService.get_current_secondary_stock(db, p.id, selected_warehouse.id)
            items.append({"product": p, "system_stock": sys_stock, "system_secondary_stock": sys_sec})

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="stocktaking.html",
        context={
            "request": request,
            "warehouses": warehouses,
            "selected_warehouse": selected_warehouse,
            "items": items,
            "msg": msg,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.post("/stocktaking")
async def process_stocktaking(
    request: Request,
    warehouse_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    form_data = await request.form()
    wh = db.query(Warehouse).filter_by(id=warehouse_id).first()
    products = db.query(Product).all()
    active_fy = InventoryService.get_active_fiscal_year(db)
    fy_id = active_fy.id if active_fy else None
    wh_currency = getattr(wh, "currency", None) or "IRR"

    adjusted_count = 0
    for p in products:
        key = f"count_{p.id}"
        if key in form_data:
            raw_val = str(form_data[key]).strip()
            # فیلد خالی به معنی عدم شمارش این ردیف کالا است
            if raw_val == "":
                continue

            try:
                phys_count = parse_float_safe(raw_val)
            except (ValueError, TypeError):
                continue

            sys_stock = InventoryService.get_current_stock(db, p.id, warehouse_id)
            diff = round(phys_count - sys_stock, 4)

            # اگر موجودی شمارش‌شده صفر باشد (phys_count == 0.0) و در سیستم موجودی مثبت وجود داشته باشد،
            # حتماً سند تعدیل کسری برای صفر کردن کامل موجودی صادر می‌شود.
            if abs(diff) > 0.0001:
                # نرخ‌گذاری بر اساس آخرین فی میانگین موزون
                avg_cost = InventoryService.get_weighted_average_cost(db, p.id, warehouse_id)
                sec_key = f"sec_count_{p.id}"
                sec_diff = None
                if sec_key in form_data and str(form_data[sec_key]).strip() != "":
                    try:
                        phys_sec = parse_float_safe(str(form_data[sec_key]).strip())
                        sys_sec = InventoryService.get_current_secondary_stock(db, p.id, warehouse_id)
                        sec_diff = round(phys_sec - sys_sec, 2)
                    except (ValueError, TypeError):
                        pass

                if diff > 0:
                    tx = StockTransaction(
                        transaction_type=TransactionType.IN,
                        transaction_source=TransactionSource.STOCKTAKING.value,
                        product_id=p.id,
                        warehouse_id=warehouse_id,
                        quantity=round(diff, 3),
                        secondary_quantity=sec_diff if sec_diff and sec_diff > 0 else None,
                        secondary_uom=p.secondary_uom,
                        unit_price=avg_cost,
                        currency=wh_currency,
                        exchange_rate=1.0,
                        status=DocumentStatus.APPROVED,
                        fiscal_year_id=fy_id,
                        reference_document=f"تعدیل مثبت انبارگردانی ({wh.name})",
                        created_by_id=current_user.id,
                        approved_by_id=current_user.id,
                        approved_at=datetime.now(timezone.utc)
                    )
                else:
                    tx = StockTransaction(
                        transaction_type=TransactionType.OUT,
                        transaction_source=TransactionSource.STOCKTAKING.value,
                        product_id=p.id,
                        warehouse_id=warehouse_id,
                        quantity=round(abs(diff), 3),
                        secondary_quantity=abs(sec_diff) if sec_diff and sec_diff < 0 else None,
                        secondary_uom=p.secondary_uom,
                        unit_price=avg_cost,
                        currency=wh_currency,
                        exchange_rate=1.0,
                        status=DocumentStatus.APPROVED,
                        fiscal_year_id=fy_id,
                        reference_document=f"تعدیل کسری انبارگردانی ({wh.name})",
                        created_by_id=current_user.id,
                        approved_by_id=current_user.id,
                        approved_at=datetime.now(timezone.utc)
                    )
                db.add(tx)
                adjusted_count += 1

    db.commit()
    msg = f"انبارگردانی انبار {wh.name} ثبت شد و {adjusted_count} قلم کالا تعدیل گردید."
    return RedirectResponse(url=f"/inventory/stocktaking?warehouse_id={warehouse_id}&msg={quote(msg)}", status_code=303)


@router.get("/stocktaking/blind-sheet", response_class=HTMLResponse)
async def get_stocktaking_blind_sheet(
    request: Request,
    warehouse_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """چاپ فرم شمارش کور انبارگردانی بدون نمایش موجودی دفتری سیستم"""
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    selected_warehouse = db.query(Warehouse).filter_by(id=warehouse_id).first() if warehouse_id else (warehouses[0] if warehouses else None)
    products = db.query(Product).filter_by(is_active=True).order_by(Product.name).all()
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="stocktaking_blind_sheet.html",
        context={
            "request": request,
            "warehouses": warehouses,
            "selected_warehouse": selected_warehouse,
            "products": products,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
            "today": format_date_localized(datetime.now(timezone.utc), region_code=active_region.code, include_time=True)
        }
    )


# ==========================================
# ۷. کاردکس ریالی و قیمت‌گذاری موجودی (Financial Kardex)
# ==========================================
@router.get("/financial-kardex/{product_id}", response_class=HTMLResponse)
async def financial_kardex(
    request: Request,
    product_id: int,
    warehouse_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter_by(id=product_id).first()
    if not product:
        return RedirectResponse(url="/inventory/balance", status_code=303)

    query = db.query(StockTransaction).filter_by(product_id=product_id).order_by(StockTransaction.created_at.asc())
    if warehouse_id:
        query = query.filter_by(warehouse_id=warehouse_id)
    raw_txs = query.all()

    entries = []
    balance_qty = 0.0
    balance_total = 0.0
    balance_rate = 0.0

    for tx in raw_txs:
        qty = tx.quantity
        price = tx.unit_price or 0.0
        
        in_qty = qty if tx.transaction_type == TransactionType.IN else 0.0
        in_price = price if in_qty > 0 else 0.0
        in_total = in_qty * in_price

        out_qty = qty if tx.transaction_type == TransactionType.OUT else 0.0
        out_price = balance_rate if out_qty > 0 else 0.0
        out_total = out_qty * out_price

        if tx.transaction_type == TransactionType.IN:
            balance_qty += in_qty
            balance_total += in_total
            balance_rate = (balance_total / balance_qty) if balance_qty > 0 else 0.0
        else:
            balance_qty = max(0.0, balance_qty - out_qty)
            balance_total = balance_qty * balance_rate

        entries.append({
            "tx": tx,
            "in_qty": in_qty,
            "in_price": in_price,
            "in_total": in_total,
            "out_qty": out_qty,
            "out_price": out_price,
            "out_total": out_total,
            "balance_qty": balance_qty,
            "balance_rate": balance_rate,
            "balance_total": balance_total
        })

    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    all_products = db.query(Product).order_by(Product.name).all()

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="financial_kardex.html",
        context={
            "request": request,
            "product": product,
            "entries": entries,
            "total_qty": balance_qty,
            "avg_unit_price": balance_rate,
            "total_financial_value": balance_total,
            "warehouses": warehouses,
            "all_products": all_products,
            "selected_warehouse_id": warehouse_id,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


# ==========================================
# ۸. چاپ رسمی سند انبار (A4 Voucher)
# ==========================================
@router.get("/transaction/{tx_id}/print", response_class=HTMLResponse)
async def print_transaction_voucher(
    request: Request,
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tx = db.query(StockTransaction).filter_by(id=tx_id).first()
    if not tx:
        return RedirectResponse(url="/inventory/transactions", status_code=303)
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="print_voucher.html",
        context={
            "request": request,
            "tx": tx,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


# ==========================================
# ۹. خروجی اکسل / CSV با پشتیبانی کامل فارسی
# ==========================================
@router.get("/export/stock")
async def export_stock_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    balances = InventoryService.calculate_stock_balances(db)
    output = io.StringIO()
    output.write('\ufeff')  # UTF-8 BOM برای باز شدن صحیح در اکسل
    writer = csv.writer(output)
    writer.writerow(["ردیف", "نام کالا", "انبار", "واحد سنجش", "مجموع ورودی", "مجموع خروجی", "موجودی فعلی"])
    for idx, b in enumerate(balances, 1):
        writer.writerow([idx, b["name"], b["warehouse"], b["uom"], b["total_in"], b["total_out"], b["current_balance"]])
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=stock_balance_export.csv"}
    )


@router.get("/export/transactions")
async def export_transactions_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    txs = db.query(StockTransaction).order_by(StockTransaction.created_at.desc()).all()
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(["کد سند", "تاریخ و زمان", "نوع عملیات", "نام کالا", "انبار", "مقدار", "واحد", "شماره پارت", "سند عطف", "ثبت کننده"])
    for t in txs:
        t_type = "ورود" if t.transaction_type == TransactionType.IN else "خروج"
        uom = t.product.uom if t.product else ""
        p_name = t.product.name if t.product else ""
        w_name = t.warehouse.name if t.warehouse else ""
        creator = t.created_by.full_name if t.created_by else ""
        date_str = t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else ""
        writer.writerow([t.id, date_str, t_type, p_name, w_name, t.quantity, uom, t.batch_number or "", t.reference_document or "", creator])

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=transactions_export.csv"}
    )


# ==========================================
# ۱۰. گردش کار و تایید / رد اسناد (Package 0-C)
# ==========================================
@router.post("/transactions/{tx_id}/approve")
async def approve_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """تایید نهایی سند و اعمال در کاردکس موجودی و به‌روزرسانی پیشرفت سفارشات خرید/فروش"""
    require_roles(current_user, {"Admin", "Warehouse_Supervisor"})

    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    if tx.status == DocumentStatus.APPROVED:
        return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} قبلاً تأیید شده است"), status_code=303)

    # اگر سند خروجی است، کنترل موجودی
    if tx.transaction_type == TransactionType.OUT:
        cur_stock = InventoryService.get_current_stock(db, tx.product_id, tx.warehouse_id)
        if tx.quantity > cur_stock:
            raise HTTPException(status_code=400, detail=f"موجودی انبار ({cur_stock}) برای تایید سند خروج #{tx.id} به مقدار {tx.quantity} کافی نیست!")

    tx.status = DocumentStatus.APPROVED
    tx.approved_by_id = current_user.id
    tx.approved_at = datetime.now(timezone.utc)

    # ۱. به‌روزرسانی سفارش خرید مرتبط (received_quantity)
    if tx.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
        if po:
            item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == tx.purchase_order_item_id).first() if tx.purchase_order_item_id else next((it for it in po.items if it.product_id == tx.product_id), None)
            if item:
                if tx.is_return:
                    # در اسناد مرجوعی خرید، مقدار از دریافتی کسر می‌شود
                    item.received_quantity = max(0.0, item.received_quantity - tx.quantity)
                else:
                    item.received_quantity += tx.quantity
            
            total_ordered = sum(it.quantity for it in po.items)
            total_rcvd = sum(it.received_quantity for it in po.items)
            if total_rcvd >= total_ordered:
                po.status = PurchaseOrderStatus.COMPLETED
            elif total_rcvd > 0:
                po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
            else:
                po.status = PurchaseOrderStatus.CONFIRMED

    # ۲. به‌روزرسانی سفارش فروش مرتبط (delivered_quantity)
    if tx.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
        if so:
            item = db.query(SalesOrderItem).filter(SalesOrderItem.id == tx.sales_order_item_id).first() if tx.sales_order_item_id else next((it for it in so.items if it.product_id == tx.product_id), None)
            if item:
                if tx.is_return:
                    # در اسناد مرجوعی فروش، مقدار از تحویلی کسر می‌شود
                    item.delivered_quantity = max(0.0, item.delivered_quantity - tx.quantity)
                else:
                    item.delivered_quantity += tx.quantity
            
            total_ordered = sum(it.quantity for it in so.items)
            total_deliv = sum(it.delivered_quantity for it in so.items)
            if total_deliv >= total_ordered:
                so.status = SalesOrderStatus.COMPLETED
            elif total_deliv > 0:
                so.status = SalesOrderStatus.PARTIALLY_DELIVERED
            else:
                so.status = SalesOrderStatus.CONFIRMED

    db.commit()

    AuditService.log(
        db, action="APPROVE", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"تأیید نهایی سند انبار #{tx.id} توسط سرپرست انبار و اعمال قطعی در موجودی و سفارشات"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} با موفقیت تایید نهایی شد"), status_code=303)


# ==========================================
# فاز ۳: سیستم اصلاحیه ورودی و خروجی (Adjustments Engine)
# ==========================================
@router.post("/transactions/{tx_id}/adjust")
async def adjust_transaction(
    tx_id: int,
    request: Request,
    new_quantity: float = Form(...),
    new_secondary_quantity: Optional[float] = Form(None),
    new_unit_price: Optional[float] = Form(None),
    adjustment_reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ثبت سند اصلاحیه ورودی/خروجی بر مبنای مابه‌التفاوت با سند مرجع"""
    require_roles(current_user, {"Admin", "Finance_Manager"})

    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند مرجع یافت نشد")
    if tx.status != DocumentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="فقط اسناد تأیید شده (APPROVED) قابل اصلاح هستند.")

    delta_q = round(new_quantity - tx.quantity, 4)
    old_sec = tx.secondary_quantity or 0.0
    delta_sec = round(new_secondary_quantity - old_sec, 2) if new_secondary_quantity is not None else None
    price_to_use = new_unit_price if (new_unit_price is not None and new_unit_price > 0) else tx.unit_price

    active_fy = db.query(FiscalYear).filter(FiscalYear.is_active == True, FiscalYear.is_closed == False).first()
    fy_id = active_fy.id if active_fy else tx.fiscal_year_id
    tx_curr = tx.currency or "IRR"
    tx_rate = tx.exchange_rate or 1.0

    # ۱. اصلاحیه سند ورودی (IN)
    if tx.transaction_type == TransactionType.IN:
        if delta_q > 0:
            # سند اصلاحیه ورودی افزایشی
            adj_tx = StockTransaction(
                transaction_type=TransactionType.IN,
                transaction_source=TransactionSource.IN_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=delta_q,
                secondary_quantity=delta_sec,
                secondary_uom=tx.secondary_uom,
                unit_price=price_to_use,
                currency=tx_curr,
                exchange_rate=tx_rate,
                parent_transaction_id=tx.id,
                purchase_order_id=tx.purchase_order_id,
                purchase_order_item_id=tx.purchase_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه افزایشی ورودی عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.now(timezone.utc)
            )
            db.add(adj_tx)
            if tx.purchase_order_id:
                po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
                if po:
                    target_item = db.query(PurchaseOrderItem).get(tx.purchase_order_item_id) if tx.purchase_order_item_id else next((it for it in po.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.received_quantity += delta_q
                    total_ordered = sum(it.quantity for it in po.items)
                    total_rcvd = sum(it.received_quantity for it in po.items)
                    if total_rcvd >= total_ordered:
                        po.status = PurchaseOrderStatus.COMPLETED
                    elif total_rcvd > 0:
                        po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
                    else:
                        po.status = PurchaseOrderStatus.CONFIRMED

        elif delta_q < 0:
            # بررسی عدم منفی شدن موجودی انبار
            abs_delta = abs(delta_q)
            cur_stock = InventoryService.get_current_stock(db, tx.product_id, tx.warehouse_id)
            if abs_delta > cur_stock:
                raise HTTPException(status_code=400, detail=f"کاهش {abs_delta} واحدی کالا باعث منفی شدن موجودی انبار می‌شود! (موجودی فعلی: {cur_stock})")
            
            # سند کاهشی با منبع IN_ADJUSTMENT
            adj_tx = StockTransaction(
                transaction_type=TransactionType.OUT,
                transaction_source=TransactionSource.IN_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=abs_delta,
                secondary_quantity=abs(delta_sec) if delta_sec else None,
                secondary_uom=tx.secondary_uom,
                unit_price=price_to_use,
                currency=tx_curr,
                exchange_rate=tx_rate,
                parent_transaction_id=tx.id,
                purchase_order_id=tx.purchase_order_id,
                purchase_order_item_id=tx.purchase_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه کاهشی ورودی عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.now(timezone.utc)
            )
            db.add(adj_tx)
            if tx.purchase_order_id:
                po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
                if po:
                    target_item = db.query(PurchaseOrderItem).get(tx.purchase_order_item_id) if tx.purchase_order_item_id else next((it for it in po.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.received_quantity = max(0.0, target_item.received_quantity - abs_delta)
                    total_ordered = sum(it.quantity for it in po.items)
                    total_rcvd = sum(it.received_quantity for it in po.items)
                    if total_rcvd >= total_ordered:
                        po.status = PurchaseOrderStatus.COMPLETED
                    elif total_rcvd > 0:
                        po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
                    else:
                        po.status = PurchaseOrderStatus.CONFIRMED

    # ۲. اصلاحیه سند خروجی (OUT)
    elif tx.transaction_type == TransactionType.OUT:
        if delta_q > 0:
            # کنترل موجودی آزاد و قابل تحویل
            avail_stock = InventoryService.get_available_stock(db, tx.product_id, tx.warehouse_id)
            if delta_q > avail_stock:
                raise HTTPException(status_code=400, detail=f"موجودی آزاد کالا ({avail_stock}) برای خروج اصلاحیه تکمیلی {delta_q} کافی نیست!")
            
            adj_tx = StockTransaction(
                transaction_type=TransactionType.OUT,
                transaction_source=TransactionSource.OUT_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=delta_q,
                secondary_quantity=delta_sec,
                secondary_uom=tx.secondary_uom,
                unit_price=price_to_use or InventoryService.get_weighted_average_cost(db, tx.product_id, tx.warehouse_id),
                currency=tx_curr,
                exchange_rate=tx_rate,
                parent_transaction_id=tx.id,
                sales_order_id=tx.sales_order_id,
                sales_order_item_id=tx.sales_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه خروجی تکمیلی عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.now(timezone.utc)
            )
            db.add(adj_tx)
            if tx.sales_order_id:
                so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
                if so:
                    target_item = db.query(SalesOrderItem).get(tx.sales_order_item_id) if tx.sales_order_item_id else next((it for it in so.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.delivered_quantity += delta_q
                    total_ordered = sum(it.quantity for it in so.items)
                    total_deliv = sum(it.delivered_quantity for it in so.items)
                    if total_deliv >= total_ordered:
                        so.status = SalesOrderStatus.COMPLETED
                    elif total_deliv > 0:
                        so.status = SalesOrderStatus.PARTIALLY_DELIVERED
                    else:
                        so.status = SalesOrderStatus.CONFIRMED

        elif delta_q < 0:
            abs_delta = abs(delta_q)
            adj_tx = StockTransaction(
                transaction_type=TransactionType.IN,
                transaction_source=TransactionSource.OUT_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=abs_delta,
                secondary_quantity=abs(delta_sec) if delta_sec else None,
                secondary_uom=tx.secondary_uom,
                unit_price=tx.unit_price,
                currency=tx_curr,
                exchange_rate=tx_rate,
                parent_transaction_id=tx.id,
                sales_order_id=tx.sales_order_id,
                sales_order_item_id=tx.sales_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه بازگشت به انبار عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.now(timezone.utc)
            )
            db.add(adj_tx)
            if tx.sales_order_id:
                so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
                if so:
                    target_item = db.query(SalesOrderItem).get(tx.sales_order_item_id) if tx.sales_order_item_id else next((it for it in so.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.delivered_quantity = max(0.0, target_item.delivered_quantity - abs_delta)
                    total_ordered = sum(it.quantity for it in so.items)
                    total_deliv = sum(it.delivered_quantity for it in so.items)
                    if total_deliv >= total_ordered:
                        so.status = SalesOrderStatus.COMPLETED
                    elif total_deliv > 0:
                        so.status = SalesOrderStatus.PARTIALLY_DELIVERED
                    else:
                        so.status = SalesOrderStatus.CONFIRMED

    # ۳. اصلاحیه صرفاً ریالی (اگر delta_q == 0 ولی قیمت تغییر کرده باشد)
    if delta_q == 0 and new_unit_price is not None and new_unit_price > 0 and new_unit_price != tx.unit_price:
        adj_tx = StockTransaction(
            transaction_type=tx.transaction_type,
            transaction_source=TransactionSource.PRICE_ADJUSTMENT.value,
            product_id=tx.product_id,
            warehouse_id=tx.warehouse_id,
            quantity=0.0,
            unit_price=new_unit_price,
            currency=tx_curr,
            exchange_rate=tx_rate,
            parent_transaction_id=tx.id,
            fiscal_year_id=fy_id,
            reference_document=f"اصلاحیه ریالی و بهای تمام‌شده سند #{tx.id}",
            notes=f"تغییر نرخ از {tx.unit_price} به {new_unit_price}. علت: {adjustment_reason}",
            status=DocumentStatus.APPROVED,
            created_by_id=current_user.id,
            approved_by_id=current_user.id,
            approved_at=datetime.now(timezone.utc)
        )
        db.add(adj_tx)
        tx.unit_price = new_unit_price

    db.commit()

    AuditService.log(
        db, action="UPDATE", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"ثبت سند اصلاحیه برای تراکنش #{tx.id}: اختلاف مقدار {delta_q}، علت: {adjustment_reason}"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند اصلاحیه برای تراکنش #{tx.id} با موفقیت ثبت و کاردکس به‌روزرسانی شد"), status_code=303)


# ==========================================
# فاز ۴: بستن سال مالی و انتقال موجودی پایان دوره به اول دوره
# ==========================================
@router.get("/fiscal-years", response_class=HTMLResponse)
async def list_fiscal_years(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مدیریت دوره‌ها و سال‌های مالی"""
    years = db.query(FiscalYear).order_by(FiscalYear.id.desc()).all()
    active_year = next((y for y in years if y.is_active and not y.is_closed), None)
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="fiscal_years.html",
        context={
            "request": request,
            "years": years,
            "active_year": active_year,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.get("/fiscal-year-close", response_class=HTMLResponse)
async def get_fiscal_year_close_review(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """صفحه پیش‌نمایش و چک‌لیست قبل از بستن سال مالی"""
    require_roles(current_user, {"Admin", "Finance_Manager"})

    active_year = db.query(FiscalYear).filter(FiscalYear.is_active == True, FiscalYear.is_closed == False).first()
    if not active_year:
        return RedirectResponse(url="/inventory/fiscal-years?msg=" + quote("سال مالی فعالی جهت بستن یافت نشد"), status_code=303)

    pending_tx_count = db.query(StockTransaction).filter(StockTransaction.status == DocumentStatus.PENDING_APPROVAL).count()
    pending_wb_count = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING).count()

    # محاسبه موجودی‌های واجد شرایط انتقال (مانده > 0.0001) و کالاهای با مانده صفر
    products = db.query(Product).filter(Product.is_active == True).all()
    warehouses = db.query(Warehouse).all()

    carry_over_items = []
    zero_balance_items = []

    for w in warehouses:
        for p in products:
            qty = InventoryService.get_current_stock(db, p.id, w.id)
            sec_qty = InventoryService.get_current_secondary_stock(db, p.id, w.id)
            avg_cost = InventoryService.get_weighted_average_cost(db, p.id, w.id)
            if qty > 0.0001:
                carry_over_items.append({
                    "product": p,
                    "warehouse": w,
                    "quantity": qty,
                    "secondary_quantity": sec_qty,
                    "avg_cost": avg_cost,
                    "total_value": qty * avg_cost
                })
            else:
                zero_balance_items.append({
                    "product": p,
                    "warehouse": w,
                    "quantity": qty
                })

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    can_close = (pending_tx_count == 0 and pending_wb_count == 0)

    return templates.TemplateResponse(
        request=request,
        name="fiscal_close.html",
        context={
            "request": request,
            "active_year": active_year,
            "pending_tx_count": pending_tx_count,
            "pending_wb_count": pending_wb_count,
            "carry_over_items": carry_over_items,
            "zero_balance_items": zero_balance_items,
            "can_close": can_close,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.post("/fiscal-year-close")
async def execute_fiscal_year_close(
    request: Request,
    new_year_name: str = Form(...),
    new_year_start_date: str = Form(...),
    new_year_end_date: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """اجرای قطعی عملیات پایان سال مالی و انتقال موجودی به دوره جدید"""
    require_roles(current_user, {"Admin", "Finance_Manager"})

    active_year = db.query(FiscalYear).filter(FiscalYear.is_active == True, FiscalYear.is_closed == False).first()
    if not active_year:
        raise HTTPException(status_code=400, detail="سال مالی فعالی جهت بستن یافت نشد.")

    # ۱. کنترل پیش‌شرط‌ها: نبود سند باز یا قبض باسکول ناتمام
    pending_tx_count = db.query(StockTransaction).filter(StockTransaction.status == DocumentStatus.PENDING_APPROVAL).count()
    if pending_tx_count > 0:
        raise HTTPException(status_code=400, detail=f"امکان بستن سال مالی وجود ندارد! تعداد {pending_tx_count} سند در انتظار تأیید در کارتابل انبار وجود دارد.")

    pending_wb_count = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING).count()
    if pending_wb_count > 0:
        raise HTTPException(status_code=400, detail=f"امکان بستن سال مالی وجود ندارد! تعداد {pending_wb_count} قبض باسکول تکمیل‌نشده (توزین اول) در سیستم وجود دارد.")

    # ۲. بستن سال مالی فعلی
    active_year.is_active = False
    active_year.is_closed = True
    active_year.closed_at = datetime.now(timezone.utc)
    active_year.closed_by_id = current_user.id

    # ۳. ایجاد سال مالی جدید
    new_fy = FiscalYear(
        name=new_year_name.strip(),
        start_date=new_year_start_date.strip(),
        end_date=new_year_end_date.strip(),
        is_active=True,
        is_closed=False
    )
    db.add(new_fy)
    db.flush()

    # ۴. انتقال مانده‌های پایان دوره به عنوان سند موجودی ابتدای دوره (OPENING_BALANCE)
    products = db.query(Product).all()
    warehouses = db.query(Warehouse).all()
    transferred_count = 0

    for w in warehouses:
        w_curr = getattr(w, "currency", None) or "IRR"
        for p in products:
            qty = InventoryService.get_current_stock(db, p.id, w.id, fiscal_year_id=active_year.id)
            # فاز ۴ بند ۳: حذف کالاهای با موجودی صفر (فقط مثبت‌ها منتقل شوند)
            if qty > 0.0001:
                sec_qty = InventoryService.get_current_secondary_stock(db, p.id, w.id, fiscal_year_id=active_year.id)
                avg_cost = InventoryService.get_weighted_average_cost(db, p.id, w.id, fiscal_year_id=active_year.id)
                op_tx = StockTransaction(
                    transaction_type=TransactionType.IN,
                    transaction_source=TransactionSource.OPENING_BALANCE.value,
                    product_id=p.id,
                    warehouse_id=w.id,
                    quantity=round(qty, 3),
                    secondary_quantity=round(sec_qty, 3) if sec_qty else None,
                    secondary_uom=p.secondary_uom,
                    unit_price=round(avg_cost, 4),
                    currency=w_curr,
                    exchange_rate=1.0,
                    status=DocumentStatus.APPROVED,
                    reference_document=f"موجودی اول دوره سال {new_fy.name} (انتقالی از {active_year.name})",
                    notes="سند افتتاحیه سیستمی پایان سال مالی",
                    fiscal_year_id=new_fy.id,
                    created_by_id=current_user.id,
                    approved_by_id=current_user.id,
                    approved_at=datetime.now(timezone.utc)
                )
                db.add(op_tx)
                transferred_count += 1

    db.commit()

    AuditService.log(
        db, action="CLOSE_FISCAL_YEAR", entity_name="FiscalYear", entity_id=str(active_year.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"بستن قطعی سال مالی {active_year.name} و افتتاح سال مالی {new_fy.name} با انتقال {transferred_count} قلم موجودی کالا"
    )

    return RedirectResponse(
        url="/inventory/fiscal-years?msg=" + quote(f"سال مالی {active_year.name} بسته شد و سال {new_fy.name} با {transferred_count} قلم سند افتتاحیه با موفقیت فعال گردید"),
        status_code=303
    )


@router.post("/transactions/{tx_id}/reject")
async def reject_transaction(
    tx_id: int,
    rejection_reason: str = Form("عدم تطابق فاکتور یا کسری بار"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """رد سند انبار با ثبت دلیل رسمی"""
    require_roles(current_user, {"Admin", "Warehouse_Supervisor"})

    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    tx.status = DocumentStatus.REJECTED
    tx.rejection_reason = rejection_reason
    db.commit()

    AuditService.log(
        db, action="REJECT", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"رد سند #{tx.id} به علت: {rejection_reason}"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} رد شد"), status_code=303)


@router.post("/transactions/{tx_id}/cancel")
async def cancel_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ابطال سند انبار"""
    require_roles(current_user, {"Admin", "Warehouse_Supervisor"})
    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    tx.status = DocumentStatus.CANCELLED
    db.commit()

    AuditService.log(
        db, action="CANCEL", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"ابطال رسمی سند انبار #{tx.id}"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} باطل گردید"), status_code=303)


# ==========================================
# ۱۱. اسناد برگشت از خرید / فروش (Package 3)
# ==========================================
@router.get("/returns/new", response_class=HTMLResponse)
async def new_return_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت سند برگشت از خرید و برگشت از فروش"""
    candidates = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer)
        )
        .filter(StockTransaction.status == DocumentStatus.APPROVED)
        .order_by(StockTransaction.created_at.desc())
        .limit(50)
        .all()
    )
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="return_form.html",
        context={
            "request": request,
            "candidate_transactions": candidates,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


@router.post("/returns")
async def process_return_transaction(
    request: Request,
    parent_transaction_id: int = Form(...),
    quantity: float = Form(...),
    return_reason: str = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ثبت سند برگشتی و اعمال در کاردکس معکوس با کنترل سقف مرجوعی و حفظ واحد فرعی"""
    parent = db.query(StockTransaction).filter(StockTransaction.id == parent_transaction_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="سند مرجع یافت نشد")

    # فاز ۵ باگ ۶: کنترل سقف مرجوعی
    already_returned = (
        db.query(func.sum(StockTransaction.quantity))
        .filter(
            StockTransaction.parent_transaction_id == parent.id,
            StockTransaction.is_return == True,
            StockTransaction.status != DocumentStatus.CANCELLED
        )
        .scalar() or 0.0
    )
    if (already_returned + quantity) > (parent.quantity + 0.0001):
        raise HTTPException(
            status_code=400,
            detail=f"مجموع مقادیر مرجوعی ({already_returned + quantity:.2f}) نمی‌تواند از مقدار کل سند مرجع ({parent.quantity:.2f}) تجاوز کند!"
        )

    # فاز ۵ باگ ۴: حفظ واحد فرعی (شاخه/بندیل) به تناسب مقدار مرجوعی
    sec_qty = (parent.secondary_quantity * (quantity / parent.quantity)) if (parent.secondary_quantity and parent.quantity > 0) else None

    rev_type = TransactionType.OUT if parent.transaction_type == TransactionType.IN else TransactionType.IN
    
    # اگر مرجوعی از نوع برگشت از خرید است (خروج از انبار)، کنترل موجودی آزاد
    if rev_type == TransactionType.OUT:
        avail_stock = InventoryService.get_available_stock(db, parent.product_id, parent.warehouse_id)
        if quantity > avail_stock:
            raise HTTPException(
                status_code=400,
                detail=f"موجودی آزاد کالا در انبار ({avail_stock}) جهت برگشت از خرید به مقدار {quantity} کافی نمی‌باشد."
            )

    active_fy = InventoryService.get_active_fiscal_year(db)
    fy_id = active_fy.id if active_fy else parent.fiscal_year_id

    return_tx = StockTransaction(
        transaction_type=rev_type,
        transaction_source=TransactionSource.RETURN.value,
        product_id=parent.product_id,
        warehouse_id=parent.warehouse_id,
        quantity=quantity,
        secondary_quantity=round(sec_qty, 2) if sec_qty else None,
        secondary_uom=parent.secondary_uom,
        unit_price=parent.unit_price,
        supplier_id=parent.supplier_id if rev_type == TransactionType.OUT else None,
        customer_id=parent.customer_id if rev_type == TransactionType.IN else None,
        purchase_order_id=parent.purchase_order_id,
        purchase_order_item_id=parent.purchase_order_item_id,
        sales_order_id=parent.sales_order_id,
        sales_order_item_id=parent.sales_order_item_id,
        reference_document=f"RET-REF#{parent.id}",
        is_return=True,
        return_reason=return_reason,
        parent_transaction_id=parent.id,
        fiscal_year_id=fy_id,
        status=DocumentStatus.PENDING_APPROVAL,
        created_by_id=current_user.id
    )
    db.add(return_tx)
    db.commit()

    AuditService.log(
        db, action="CREATE", entity_name="StockTransaction", entity_id=str(return_tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"ثبت سند برگشتی موقت #{return_tx.id} عطف به سند #{parent.id} و ارسال به کارتابل انبار"
    )

    return RedirectResponse(
        url="/inventory/transactions?msg=" + quote(f"سند برگشتی #{return_tx.id} با موفقیت ثبت شد و جهت تایید نهایی به کارتابل انبار ارسال گردید."),
        status_code=303
    )


# ==========================================
# ۱۲. شناسنامه متالورژی MTC (Package 9)
# ==========================================
@router.get("/transactions/{tx_id}/mtc", response_class=HTMLResponse)
async def view_mtc_certificate(
    tx_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """چاپ رسمی شناسنامه کیفیت و متالورژی کالا"""
    tx = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer),
            joinedload(StockTransaction.warehouse)
        )
        .filter(StockTransaction.id == tx_id)
        .first()
    )
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="mtc_certificate.html",
        context={
            "request": request,
            "tx": tx,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )


# ==========================================
# ۱۳. چاپ لیبل بارکد بندیل و پالت (Package 10)
# ==========================================
@router.get("/products/{product_id}/label", response_class=HTMLResponse)
async def view_barcode_label(
    product_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """چاپ برچسب بارکد استاندارد لیبل‌پرینتر"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="کالا یافت نشد")
    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")
    return templates.TemplateResponse(
        request=request,
        name="barcode_label.html",
        context={
            "request": request,
            "product": product,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )