from typing import Optional
from urllib.parse import quote
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from src.infrastructure.database import get_db
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import BaggingOrder, Product, Warehouse, StockTransaction, TransactionType
from src.domain_model.enums import BaggingStatus, DocumentStatus
from src.services.audit_service import AuditService
from src.services.inventory_service import InventoryService
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(prefix="/bagging", tags=["Bagging Operations"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("", response_class=HTMLResponse)
async def list_bagging_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """لیست و داشبورد عملیات کیسه‌گیری فله به جامبوبگ اوره و کودهای شیمیایی"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    orders = (
        db.query(BaggingOrder)
        .options(
            joinedload(BaggingOrder.bulk_product),
            joinedload(BaggingOrder.packaged_product)
        )
        .order_by(BaggingOrder.created_at.desc())
        .all()
    )

    total_bulk_tonnage = sum(o.bulk_tonnage_used for o in orders)
    total_packages = sum(o.packages_produced for o in orders)

    return templates.TemplateResponse(
        request=request,
        name="bagging.html",
        context={
            "request": request,
            "orders": orders,
            "total_bulk_tonnage": total_bulk_tonnage,
            "total_packages": total_packages,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_bagging_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت دستور کیسه‌گیری فله به جامبوبگ یا کیسه ۵۰ کیلویی"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    products = db.query(Product).filter_by(is_active=True).all()
    warehouses = db.query(Warehouse).all()
    count = db.query(BaggingOrder).count() + 1
    generated_bag_number = f"BAG-TR-{count:04d}" if is_tr else f"BAG-1403-{count:04d}"

    return templates.TemplateResponse(
        request=request,
        name="bagging_form.html",
        context={
            "request": request,
            "generated_bag_number": generated_bag_number,
            "products": products,
            "warehouses": warehouses,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_bagging_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_number: str = Form(...),
    bulk_product_id: int = Form(...),
    packaged_product_id: int = Form(...),
    warehouse_id: int = Form(...),
    bulk_tonnage_used: float = Form(...),
    packages_produced: float = Form(...),
    package_type: str = Form("جامبوبگ ۱ تنی"),
    packaging_cost_per_ton: float = Form(0.0),
    waste_tonnage: float = Form(0.0),
    notes: Optional[str] = Form(None)
):
    """ثبت دستور کیسه‌گیری و کسر خودکار فله و افزایش محصول بسته‌بندی شده در انبار"""
    try:
        # ۱. کنترل موجودی آزاد کالای فله در انبار
        avail = InventoryService.get_available_stock(db, bulk_product_id, warehouse_id)
        if bulk_tonnage_used > avail:
            raise HTTPException(
                status_code=400,
                detail=f"موجودی آزاد کالای فله در انبار ({avail}) کمتر از تناژ درخواستی جهت کیسه‌گیری ({bulk_tonnage_used}) است."
            )

        # ۲. کنترل توازن جرم
        if waste_tonnage < 0 or waste_tonnage > bulk_tonnage_used:
            raise HTTPException(
                status_code=400,
                detail="تناژ ضایعات کیسه‌گیری نامعتبر است (نمی‌تواند منفی یا بیشتر از کل تناژ فله مصرفی باشد)."
            )

        active_fy = InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        avg_cost = InventoryService.get_weighted_average_cost(db, bulk_product_id, warehouse_id)

        bag_order = BaggingOrder(
            order_number=order_number.strip(),
            bulk_product_id=bulk_product_id,
            packaged_product_id=packaged_product_id,
            bulk_tonnage_used=bulk_tonnage_used,
            packages_produced=packages_produced,
            package_type=package_type.strip(),
            waste_tonnage=waste_tonnage,
            packaging_cost_per_ton=packaging_cost_per_ton,
            status=BaggingStatus.COMPLETED,
            notes=notes.strip() if notes else None
        )
        db.add(bag_order)

        # ۳. کسر اوره فله از انبار (StockTransaction OUT)
        tx_bulk_out = StockTransaction(
            transaction_type=TransactionType.OUT,
            transaction_source=TransactionSource.INTERNAL_USE.value,
            product_id=bulk_product_id,
            warehouse_id=warehouse_id,
            quantity=bulk_tonnage_used,
            unit_price=avg_cost,
            reference_document=order_number.strip(),
            status=DocumentStatus.APPROVED,
            fiscal_year_id=fy_id,
            created_by_id=current_user.id
        )
        db.add(tx_bulk_out)

        # ۴. افزایش محصول بسته‌بندی‌شده به انبار (StockTransaction IN)
        target_prod = db.query(Product).filter(Product.id == packaged_product_id).first()
        in_qty = packages_produced if (target_prod and target_prod.uom in ("کیسه", "عدد")) else (bulk_tonnage_used - waste_tonnage)
        effective_cost = ((avg_cost * bulk_tonnage_used) + (packaging_cost_per_ton * bulk_tonnage_used)) / in_qty if in_qty > 0 else avg_cost

        tx_pkg_in = StockTransaction(
            transaction_type=TransactionType.IN,
            transaction_source=TransactionSource.INTERNAL_USE.value,
            product_id=packaged_product_id,
            warehouse_id=warehouse_id,
            quantity=in_qty,
            secondary_quantity=packages_produced,
            secondary_uom=package_type,
            unit_price=effective_cost,
            reference_document=order_number.strip(),
            status=DocumentStatus.APPROVED,
            fiscal_year_id=fy_id,
            created_by_id=current_user.id
        )
        db.add(tx_pkg_in)

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="BaggingOrder",
            entity_id=str(bag_order.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"عملیات کیسه‌گیری {bag_order.order_number}: مصرف {bulk_tonnage_used} تن فله و تولید {packages_produced} {package_type}"
        )

        active_region = get_active_region(request)
        is_tr = (active_region.code == Region.TR)
        msg_text = f"Torbalama emri {bag_order.order_number} tamamlandı ve stok güncellendi" if is_tr else f"عملیات کیسه‌گیری {bag_order.order_number} انجام شد و موجودی انبار به‌روزرسانی گردید"

        return RedirectResponse(
            url="/bagging?msg=" + quote(msg_text),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در ثبت عملیات کیسه‌گیری: {str(e)}")
