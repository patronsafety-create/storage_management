from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from urllib.parse import quote

from src.core.dependencies import get_db, require_admin, get_current_user
from src.domain_model.inventory_models import Product, Warehouse
from src.domain_model.auth_models import User

router = APIRouter(
    prefix="/master-data",
    tags=["Master Data"],
    dependencies=[Depends(require_admin)]
)
templates = Jinja2Templates(directory="templates")


@router.post("/product")
async def create_product(
    name: str = Form(...),
    uom: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        db.add(Product(name=name.strip(), uom=uom.strip()))
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
        db.add(Warehouse(name=name.strip()))
        db.commit()
        return RedirectResponse(url="/dashboard?msg=" + quote("انبار جدید با موفقیت ثبت شد"), status_code=303)
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/dashboard?error=" + quote("این انبار از قبل در سیستم وجود دارد"), status_code=303)