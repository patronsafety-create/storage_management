from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urllib.parse import quote

from src.infrastructure.database import get_db
from src.domain_model.inventory_models import Product, Warehouse
from src.api.auth import get_current_user

# قفل امنیتی فرم‌های پاپ‌آپ ایجاد کالا و انبار
router = APIRouter(
    prefix="/master-data", 
    tags=["Master Data"],
    dependencies=[Depends(get_current_user)]
)

@router.post("/product")
async def create_product(
    name: str = Form(...),
    uom: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        new_product = Product(name=name.strip(), uom=uom.strip())
        db.add(new_product)
        db.commit()
        return RedirectResponse(url="/dashboard?msg=" + quote("کالای جدید با موفقیت ثبت شد"), status_code=303)
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/dashboard?error=" + quote("این کالا از قبل در سیستم وجود دارد"), status_code=303)

@router.post("/warehouse")
async def create_warehouse(
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        new_warehouse = Warehouse(name=name.strip())
        db.add(new_warehouse)
        db.commit()
        return RedirectResponse(url="/dashboard?msg=" + quote("انبار جدید با موفقیت ثبت شد"), status_code=303)
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/dashboard?error=" + quote("این انبار از قبل در سیستم وجود دارد"), status_code=303)