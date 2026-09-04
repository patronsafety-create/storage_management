from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

# اتصال به زیرساخت دیتابیس و مدل‌ها
from src.infrastructure.database import get_db
from src.domain_model.inventory_models import StockTransaction

router = APIRouter(tags=["UI"])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """
    رندر داشبورد با داده‌های زنده از پایگاه‌داده
    """
    # محاسبه تعداد کل اسناد انبار
    transaction_count = db.query(StockTransaction).count()

    # دریافت ۵ تراکنش آخر برای نمایش در جدول گزارشات سریع
    recent_transactions = db.query(StockTransaction)\
        .order_by(StockTransaction.created_at.desc())\
        .limit(5).all()

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "request": request, 
            "tx_count": transaction_count,
            "recent_txs": recent_transactions
        }
    )