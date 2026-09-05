from fastapi import APIRouter, Depends, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urllib.parse import quote

# فراخوانی قفل مخصوص ادمین از هسته مرکزی
from src.core.dependencies import get_db, require_admin
from src.domain_model.inventory_models import Product, Warehouse

# 🌟 اعمال قفل مدیر: هیچ اپراتوری حتی با دانستن آدرس نمی‌تواند به این مسیرها درخواست بفرستد
router = APIRouter(
    prefix="/master-data", 
    tags=["Master Data"],
    dependencies=[Depends(require_admin)]
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