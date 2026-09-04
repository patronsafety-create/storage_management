from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from src.infrastructure.database import get_db
from src.domain_model.inventory_models import StockTransaction

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    msg: Optional[str] = None,    # دریافت پیام موفقیت از URL
    error: Optional[str] = None,  # دریافت پیام خطا از URL
    db: Session = Depends(get_db)
):
    transaction_count = db.query(StockTransaction).count()

    recent_transactions = db.query(StockTransaction)\
        .order_by(StockTransaction.created_at.desc())\
        .limit(5).all()

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "request": request, 
            "tx_count": transaction_count,
            "recent_txs": recent_transactions,
            "msg": msg,      # ارسال به HTML
            "error": error   # ارسال به HTML
        }
    )