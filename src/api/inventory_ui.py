from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, case
from typing import Optional

# فراخوانی مدیریت نشست دیتابیس و مدل‌های تجاری انبار
from src.infrastructure.database import get_db
from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType

router = APIRouter(prefix="/inventory", tags=["Inventory UI"])
templates = Jinja2Templates(directory="templates")

@router.get("/transaction", response_class=HTMLResponse)
async def get_transaction_form(request: Request, db: Session = Depends(get_db)):
    """
    رندر فرم ثبت رسید و حواله با داده‌های واقعی از دیتابیس
    """
    products = db.query(Product).all()
    warehouses = db.query(Warehouse).all()

    return templates.TemplateResponse(
        request=request, 
        name="transaction_form.html", 
        context={
            "request": request,
            "products": products,
            "warehouses": warehouses
        }
    )

@router.post("/transaction")
async def process_transaction(
    request: Request,
    transaction_type: str = Form(...),
    product_id: int = Form(...),
    warehouse_id: int = Form(...),
    quantity: float = Form(...),
    batch_number: Optional[str] = Form(None),
    reference_document: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    دریافت داده‌های فرم، اعتبارسنجی و ثبت امن در پایگاه‌داده با حفظ ACID
    """
    try:
        tx_enum = TransactionType.IN if transaction_type == "IN" else TransactionType.OUT
        
        new_transaction = StockTransaction(
            transaction_type=tx_enum,
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            batch_number=batch_number,
            reference_document=reference_document
        )
        
        db.add(new_transaction)
        db.commit() 
        
        return RedirectResponse(url="/dashboard", status_code=303)
        
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="transaction_form.html",
            context={
                "request": request,
                "products": db.query(Product).all(),
                "warehouses": db.query(Warehouse).all(),
                "error": "خطای یکپارچگی داده: مقدار یا نوع تراکنش نامعتبر است."
            },
            status_code=400
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="transaction_form.html",
            context={
                "request": request,
                "products": db.query(Product).all(),
                "warehouses": db.query(Warehouse).all(),
                "error": "خطای سیستمی در ثبت تراکنش رخ داده است."
            },
            status_code=500
        )

@router.get("/balance", response_class=HTMLResponse)
async def get_stock_balance(request: Request, db: Session = Depends(get_db)):
    """
    محاسبه و رندر گزارش ترازنامه انبار (موجودی لحظه‌ای)
    """
    balance_query = db.query(
        Product.name.label("product_name"),
        Product.uom.label("uom"),
        func.coalesce(
            func.sum(case((StockTransaction.transaction_type == TransactionType.IN, StockTransaction.quantity), else_=0)), 0
        ).label('total_in'),
        func.coalesce(
            func.sum(case((StockTransaction.transaction_type == TransactionType.OUT, StockTransaction.quantity), else_=0)), 0
        ).label('total_out')
    ).outerjoin(StockTransaction, Product.id == StockTransaction.product_id) \
     .group_by(Product.id, Product.name, Product.uom).all()

    stock_balances = []
    for row in balance_query:
        stock_balances.append({
            "name": row.product_name,
            "uom": row.uom,
            "total_in": row.total_in,
            "total_out": row.total_out,
            "current_balance": row.total_in - row.total_out
        })

    return templates.TemplateResponse(
        request=request,
        name="stock_balance.html",
        context={
            "request": request,
            "stock_balances": stock_balances
        }
    )