import csv
import io
from urllib.parse import quote
from typing import Optional

from fastapi import APIRouter, Request, Depends, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.core.dependencies import get_db, get_current_user
from src.services.inventory_service import InventoryService
from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType
from src.domain_model.auth_models import User

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
    products = db.query(Product).order_by(Product.name).all()
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()
    return templates.TemplateResponse(
        request=request,
        name="transaction_form.html",
        context={
            "request": request,
            "products": products,
            "warehouses": warehouses,
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
    batch_number: Optional[str] = Form(None),
    reference_document: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    def error_response(msg: str):
        return templates.TemplateResponse(
            request=request,
            name="transaction_form.html",
            context={
                "request": request,
                "products": db.query(Product).order_by(Product.name).all(),
                "warehouses": db.query(Warehouse).order_by(Warehouse.name).all(),
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
        new_transaction = StockTransaction(
            transaction_type=tx_enum,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            unit_price=unit_price or 0.0,
            batch_number=batch_number or None,
            reference_document=reference_document or None,
            created_by_id=current_user.id
        )
        db.add(new_transaction)
        db.commit()
        return RedirectResponse(url="/dashboard?msg=" + quote("تراکنش انبار با موفقیت ثبت شد"), status_code=303)

    except IntegrityError:
        db.rollback()
        return error_response("خطای یکپارچگی داده: مقدار یا نوع تراکنش نامعتبر است.")
    except Exception:
        db.rollback()
        return error_response("خطای سیستمی در ثبت تراکنش رخ داده است.")


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
    query = db.query(StockTransaction).order_by(StockTransaction.created_at.desc())

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