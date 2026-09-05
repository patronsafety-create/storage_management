from fastapi import APIRouter, Request, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional

# 🌟 فراخوانی وابستگی‌های هسته و لایه سرویس جدید
from src.core.dependencies import get_db, get_current_user
from src.services.inventory_service import InventoryService

from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType
from src.domain_model.user_models import User

router = APIRouter(
    prefix="/inventory", 
    tags=["Inventory UI"],
    dependencies=[Depends(get_current_user)]
)
templates = Jinja2Templates(directory="templates")

@router.get("/transaction", response_class=HTMLResponse)
async def get_transaction_form(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    products = db.query(Product).all()
    warehouses = db.query(Warehouse).all()

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
    batch_number: Optional[str] = Form(None),
    reference_document: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
                "error": "خطای یکپارچگی داده: مقدار یا نوع تراکنش نامعتبر است.",
                "user": current_user
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
                "error": "خطای سیستمی در ثبت تراکنش رخ داده است.",
                "user": current_user
            },
            status_code=500
        )

@router.get("/balance", response_class=HTMLResponse)
async def get_stock_balance(
    request: Request, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 🌟 استفاده مستقیم از لایه سرویس - کنترلر کاملاً سبک و خوانا شد
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