import csv
import io
from urllib.parse import quote
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Depends, Form, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from src.core.dependencies import get_db, get_current_user
from src.services.inventory_service import InventoryService
from src.services.audit_service import AuditService
from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType, Supplier, Customer
from src.domain_model.auth_models import User
from src.domain_model.enums import DocumentStatus

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory UI"],
    dependencies=[Depends(get_current_user)]
)
templates = Jinja2Templates(directory="templates")

ITEMS_PER_PAGE = 10


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

    return templates.TemplateResponse(
        request=request,
        name="transaction_form.html",
        context={
            "request": request,
            "products": products,
            "warehouses": warehouses,
            "suppliers": suppliers,
            "customers": customers,
            "user": current_user
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
    # ۲. موتور دو واحدی (Package 4)
    secondary_quantity: Optional[float] = Form(None),
    secondary_uom: Optional[str] = Form(None),
    # ۶. بهای تمام شده و لجستیک (Package 6)
    freight_cost: Optional[float] = Form(0.0),
    insurance_cost: Optional[float] = Form(0.0),
    weighbridge_cost: Optional[float] = Form(0.0),
    bill_of_lading_qty: Optional[float] = Form(None),
    # ۹. شجره‌نامه ذوب و متالورژی (Package 9)
    heat_number: Optional[str] = Form(None),
    mtc_number: Optional[str] = Form(None),
    chemical_analysis: Optional[str] = Form(None),
    mechanical_analysis: Optional[str] = Form(None),
    # ۱۲. سامانه تجارت (Package 12)
    waybill_number: Optional[str] = Form(None),
    tracking_code: Optional[str] = Form(None),
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
                "error": msg,
                "user": current_user
            },
            status_code=400
        )

    try:
        if transaction_type == "OUT":
            current_stock = InventoryService.get_current_stock(db, product_id, warehouse_id)
            if quantity > current_stock:
                return error_response(
                    f"عملیات غیرمجاز! موجودی فعلی {current_stock} است "
                    f"و امکان صدور حواله برای {quantity} وجود ندارد."
                )

        tx_enum = TransactionType.IN if transaction_type == "IN" else TransactionType.OUT

        # محاسبات دو واحدی دینامیک
        weight_per_unit = (quantity / secondary_quantity) if (secondary_quantity and secondary_quantity > 0) else None
        prod = db.query(Product).filter(Product.id == product_id).first()
        std_w = prod.nominal_weight if (prod and prod.nominal_weight) else None
        deviation_pct = None
        if weight_per_unit and std_w and std_w > 0:
            deviation_pct = round(((weight_per_unit - std_w) / std_w) * 100.0, 2)

        # محاسبات بهای تمام‌شده و تلورانس بارنامه
        shrink_qty = max(0.0, bill_of_lading_qty - quantity) if (bill_of_lading_qty and bill_of_lading_qty > quantity) else 0.0
        shrink_pct = (shrink_qty / bill_of_lading_qty * 100.0) if (bill_of_lading_qty and bill_of_lading_qty > 0) else 0.0
        penalty = (shrink_qty * (unit_price or 1000.0)) if shrink_pct > 0.3 else 0.0
        total_landed = (quantity * (unit_price or 0.0)) + (freight_cost or 0.0) + (insurance_cost or 0.0) + (weighbridge_cost or 0.0)

        # وضعیت سند
        status_enum = DocumentStatus[doc_status] if (doc_status and doc_status in DocumentStatus.__members__) else DocumentStatus.APPROVED

        new_transaction = StockTransaction(
            transaction_type=tx_enum,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            unit_price=unit_price or 0.0,
            supplier_id=supplier_id if tx_enum == TransactionType.IN and supplier_id and supplier_id > 0 else None,
            customer_id=customer_id if tx_enum == TransactionType.OUT and customer_id and customer_id > 0 else None,
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
            details=f"ثبت سند {tx_enum.value} به مقدار {quantity} {prod.uom if prod else ''} در {new_transaction.warehouse_id}"
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
    return templates.TemplateResponse(
        request=request,
        name="stock_balance.html",
        context={
            "request": request,
            "stock_balances": stock_balances,
            "user": current_user
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
            "user": current_user
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
    return templates.TemplateResponse(
        request=request,
        name="transfer_form.html",
        context={
            "request": request,
            "products": products,
            "warehouses": warehouses,
            "user": current_user
        }
    )


@router.post("/transfer")
async def process_transfer(
    request: Request,
    product_id: int = Form(...),
    from_warehouse_id: int = Form(...),
    to_warehouse_id: int = Form(...),
    quantity: float = Form(...),
    reference_document: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    def error_response(msg: str):
        return templates.TemplateResponse(
            request=request,
            name="transfer_form.html",
            context={
                "request": request,
                "products": db.query(Product).order_by(Product.name).all(),
                "warehouses": db.query(Warehouse).order_by(Warehouse.name).all(),
                "error": msg,
                "user": current_user
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
    ref = reference_document or f"TRF-{from_warehouse_id}-to-{to_warehouse_id}"

    # خروج از مبدأ
    tx_out = StockTransaction(
        transaction_type=TransactionType.OUT,
        product_id=product_id,
        warehouse_id=from_warehouse_id,
        quantity=quantity,
        reference_document=f"{ref} (انتقال به {to_wh.name})",
        created_by_id=current_user.id
    )
    # ورود به مقصد
    tx_in = StockTransaction(
        transaction_type=TransactionType.IN,
        product_id=product_id,
        warehouse_id=to_warehouse_id,
        quantity=quantity,
        reference_document=f"{ref} (انتقال از {from_wh.name})",
        created_by_id=current_user.id
    )
    db.add_all([tx_out, tx_in])
    db.commit()
    return RedirectResponse(url="/dashboard?msg=" + quote("انتقال بین انبارها با موفقیت ثبت شد"), status_code=303)


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
            items.append({"product": p, "system_stock": sys_stock})

    return templates.TemplateResponse(
        request=request,
        name="stocktaking.html",
        context={
            "request": request,
            "warehouses": warehouses,
            "selected_warehouse": selected_warehouse,
            "items": items,
            "msg": msg,
            "user": current_user
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

    adjusted_count = 0
    for p in products:
        key = f"count_{p.id}"
        if key in form_data:
            try:
                phys_count = float(form_data[key])
            except ValueError:
                continue
            sys_stock = InventoryService.get_current_stock(db, p.id, warehouse_id)
            diff = phys_count - sys_stock
            if abs(diff) > 0.0001:
                if diff > 0:
                    tx = StockTransaction(
                        transaction_type=TransactionType.IN,
                        product_id=p.id,
                        warehouse_id=warehouse_id,
                        quantity=round(diff, 3),
                        reference_document=f"تعدیل مثبت انبارگردانی ({wh.name})",
                        created_by_id=current_user.id
                    )
                else:
                    tx = StockTransaction(
                        transaction_type=TransactionType.OUT,
                        product_id=p.id,
                        warehouse_id=warehouse_id,
                        quantity=round(abs(diff), 3),
                        reference_document=f"تعدیل کسری انبارگردانی ({wh.name})",
                        created_by_id=current_user.id
                    )
                db.add(tx)
                adjusted_count += 1

    db.commit()
    msg = f"انبارگردانی انبار {wh.name} ثبت شد و {adjusted_count} قلم کالا تعدیل گردید."
    return RedirectResponse(url=f"/inventory/stocktaking?warehouse_id={warehouse_id}&msg={quote(msg)}", status_code=303)


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
            "user": current_user
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
    return templates.TemplateResponse(
        request=request,
        name="print_voucher.html",
        context={"request": request, "tx": tx, "user": current_user}
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
    """تایید نهایی سند و اعمال در کاردکس موجودی توسط مدیر انبار"""
    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    tx.status = DocumentStatus.APPROVED
    tx.approved_by_id = current_user.id
    tx.approved_at = datetime.now()
    db.commit()

    AuditService.log(
        db, action="APPROVE", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"تأیید نهایی سند انبار #{tx.id} توسط سرپرست/مدیر انبار"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} با موفقیت تایید نهایی شد"), status_code=303)


@router.post("/transactions/{tx_id}/reject")
async def reject_transaction(
    tx_id: int,
    rejection_reason: str = Form("عدم تطابق فاکتور یا کسری بار"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """رد سند انبار با ثبت دلیل رسمی"""
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
    return templates.TemplateResponse(
        request=request,
        name="return_form.html",
        context={
            "request": request,
            "candidate_transactions": candidates,
            "user": current_user
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
    """ثبت سند برگشتی و اعمال در کاردکس معکوس"""
    parent = db.query(StockTransaction).filter(StockTransaction.id == parent_transaction_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="سند مرجع یافت نشد")

    rev_type = TransactionType.OUT if parent.transaction_type == TransactionType.IN else TransactionType.IN

    return_tx = StockTransaction(
        transaction_type=rev_type,
        product_id=parent.product_id,
        warehouse_id=parent.warehouse_id,
        quantity=quantity,
        unit_price=parent.unit_price,
        supplier_id=parent.supplier_id if rev_type == TransactionType.OUT else None,
        customer_id=parent.customer_id if rev_type == TransactionType.IN else None,
        reference_document=f"RET-REF#{parent.id}",
        is_return=True,
        return_reason=return_reason,
        parent_transaction_id=parent.id,
        status=DocumentStatus.APPROVED,
        created_by_id=current_user.id
    )
    db.add(return_tx)
    db.commit()

    AuditService.log(
        db, action="CREATE", entity_name="StockTransaction", entity_id=str(return_tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"ثبت سند برگشتی #{return_tx.id} عطف به سند #{parent.id} به علت: {return_reason}"
    )

    return RedirectResponse(
        url="/inventory/transactions?msg=" + quote(f"سند برگشتی #{return_tx.id} با موفقیت ثبت و کاردکس اصلاح شد"),
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
    return templates.TemplateResponse(
        request=request,
        name="mtc_certificate.html",
        context={"request": request, "tx": tx, "user": current_user}
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
    return templates.TemplateResponse(
        request=request,
        name="barcode_label.html",
        context={"request": request, "product": product, "user": current_user}
    )