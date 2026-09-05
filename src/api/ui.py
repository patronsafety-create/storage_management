from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import Optional

from src.core.dependencies import get_db, get_current_user

from src.domain_model.inventory_models import StockTransaction
from src.domain_model.user_models import User

router = APIRouter(tags=["UI"], dependencies=[Depends(get_current_user)])
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request, 
    msg: Optional[str] = None,    
    error: Optional[str] = None,  
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction_count = db.query(StockTransaction).count()

    recent_transactions = (
        db.query(StockTransaction)
        .order_by(StockTransaction.created_at.desc())
        .limit(5)
        .all()
    )

    # 🌟 بررسی نقش در لایه سرور به جای HTML
    is_admin = any(role.name == "Admin" for role in current_user.roles)

    return templates.TemplateResponse(
        request=request, 
        name="dashboard.html", 
        context={
            "request": request, 
            "tx_count": transaction_count,
            "recent_txs": recent_transactions,
            "msg": msg,      
            "error": error,
            "user": current_user,
            "is_admin": is_admin  # ارسال مستقیم نتیجه به قالب
        }
    )