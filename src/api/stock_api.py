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
    """موجودی لحظه‌ای و آزاد یک کالا در یک انبار — برای نمایش AJAX در فرم‌ها و اعتبارسنجی خروج"""
    current_stock = InventoryService.get_current_stock(db, product_id, warehouse_id)
    available_stock = InventoryService.get_available_stock(db, product_id, warehouse_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    return JSONResponse({
        "current_stock": round(current_stock, 3),
        "available_stock": round(available_stock, 3),
        "product_name": product.name if product else "",
        "uom": product.uom if product else ""
    })


@router.get("/stock/{product_id}")
async def get_product_total_stock(
    product_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """مجموع موجودی یک کالا در تمامی انبارهای فعال"""
    total_stock = InventoryService.get_total_stock_all_warehouses(db, product_id)
    product = db.query(Product).filter(Product.id == product_id).first()
    return JSONResponse({
        "total_stock": round(total_stock, 3),
        "product_name": product.name if product else "",
        "uom": product.uom if product else ""
    })
