"""
API موجودی لحظه‌ای — برای فراخوانی AJAX از فرم تراکنش
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.core.dependencies import get_db, get_current_user
from src.domain_model.inventory_models import Product
from src.services.inventory_service import InventoryService

router = APIRouter(prefix="/api", tags=["Stock API"])


@router.get("/stock/{product_id}/{warehouse_id}")
async def get_stock(
    product_id: int,
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """موجودی لحظه‌ای یک کالا در یک انبار — برای نمایش AJAX در فرم"""
    current_stock = InventoryService.get_current_stock(db, product_id, warehouse_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    return JSONResponse({
        "current_stock": round(current_stock, 3),
        "uom": product.uom if product else ""
    })
