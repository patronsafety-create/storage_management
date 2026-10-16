from typing import Optional
from urllib.parse import quote
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from src.infrastructure.database import get_db
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import CuttingOrder, Product, Warehouse, StockTransaction, TransactionType
from src.domain_model.enums import CuttingStatus, DocumentStatus
from src.services.audit_service import AuditService
from src.services.inventory_service import InventoryService
from src.core.localization.regions import get_active_region, Region, localize_display_name
from src.core.dependencies import allow_roles, require_module

router = APIRouter(
    prefix="/cutting",
    tags=["Cutting & Remnants"],
    dependencies=[
        Depends(require_module("cutting")),
        Depends(allow_roles("Admin", "Warehouse_Supervisor"))
    ]
)
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name



@router.get("", response_class=HTMLResponse)
async def list_cutting_orders(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """لیست دستورات برش آهن‌آلات و انبار قطعات ته‌شاخه و پرتی"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    orders = (
        db.query(CuttingOrder)
        .options(joinedload(CuttingOrder.product))
        .order_by(CuttingOrder.created_at.desc())
        .all()
    )

    # قطعات ته‌شاخه قابل استفاده موجود
    remnants = [o for o in orders if o.remnant_length >= 1.0 and o.status == CuttingStatus.COMPLETED]
    scraps = [o for o in orders if o.remnant_length < 1.0 and o.status == CuttingStatus.COMPLETED]

    return templates.TemplateResponse(
        request=request,
        name="cutting.html",
        context={
            "request": request,
            "orders": orders,
            "remnants": remnants,
            "scraps": scraps,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_cutting_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت دستور برش شاخه ۱۲ متری به قطعات سفارشی"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    products = db.query(Product).filter_by(is_active=True).all()
    count = db.query(CuttingOrder).count() + 1
    generated_cut_number = f"CUT-TR-{count:04d}" if is_tr else f"CUT-1403-{count:04d}"

    return templates.TemplateResponse(
        request=request,
        name="cutting_form.html",
        context={
            "request": request,
            "generated_cut_number": generated_cut_number,
            "products": products,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_cutting_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_number: str = Form(...),
    product_id: int = Form(...),
    original_length: float = Form(12.0),
    cut_length: float = Form(...),
    pieces_count: int = Form(1),
    notes: Optional[str] = Form(None)
):
    """ثبت دستور برش و تفکیک خودکار ته‌شاخه یا ضایعات"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    try:
        total_cut = cut_length * pieces_count
        if total_cut > original_length:
            detail_msg = "Kesilen parçaların toplam boyu ana profil boyunu aşamaz!" if is_tr else "مجموع طول قطعات برش‌خورده بیشتر از طول شاخه مادر است!"
            raise HTTPException(status_code=400, detail=detail_msg)

        remnant_len = original_length - total_cut
        if is_tr:
            destination = "Parça / Kalan Profil Deposu" if remnant_len >= 1.0 else "Hurda Deposu"
        else:
            destination = "انبار ته‌شاخه‌ها" if remnant_len >= 1.0 else "انبار ضایعات آهن"

        # برآورد وزن ته‌شاخه بر مبنای طول
        p = db.query(Product).filter(Product.id == product_id).first()
        remnant_weight = 0.0
        if p and p.nominal_weight and p.length and p.length > 0:
            remnant_weight = (p.nominal_weight / p.length) * remnant_len

        cutting = CuttingOrder(
            order_number=order_number.strip(),
            product_id=product_id,
            original_length=original_length,
            cut_length=cut_length,
            pieces_count=pieces_count,
            remnant_length=remnant_len,
            remnant_weight=remnant_weight,
            destination=destination,
            status=CuttingStatus.COMPLETED,
            notes=notes.strip() if notes else None
        )
        db.add(cutting)
        db.flush()

        # اتصال کارگاه برش به کاردکس انبار (صدور سند خروج شاخه مادر و ورود ته‌شاخه)
        wh = db.query(Warehouse).first()
        wh_id = wh.id if wh else 1
        is_ton = p and p.uom in ('تن', 'Ton', 'ton')
        mother_qty = ((p.nominal_weight or 1000.0) / 1000.0) if is_ton else (p.nominal_weight or 1.0)

        # کنترل موجودی آزاد شاخه مادر در انبار
        avail = InventoryService.get_available_stock(db, product_id, wh_id)
        if mother_qty > avail:
            detail_msg = f"Ana profil için serbest depo stoku yetersiz! (Mevcut: {avail}, Gerekli: {mother_qty})" if is_tr else f"موجودی آزاد شاخه مادر در انبار کافی نیست! (موجودی آزاد: {avail}، مورد نیاز: {mother_qty})"
            raise HTTPException(status_code=400, detail=detail_msg)

        active_fy = InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        avg_cost = InventoryService.get_weighted_average_cost(db, product_id, wh_id)

        wh_obj = db.query(Warehouse).get(wh_id)
        wh_currency = getattr(wh_obj, "currency", None) or "IRR"

        # خروج شاخه مادر از انبار
        tx_out = StockTransaction(
            transaction_type=TransactionType.OUT,
            transaction_source="CUTTING",
            product_id=product_id,
            warehouse_id=wh_id,
            quantity=round(mother_qty, 3),
            secondary_quantity=1.0,
            secondary_uom='شاخه',
            unit_price=avg_cost,
            currency=wh_currency,
            exchange_rate=1.0,
            status=DocumentStatus.APPROVED,
            fiscal_year_id=fy_id,
            reference_document=f"برش شاخه مادر - دستور {cutting.order_number}",
            created_by_id=current_user.id,
            approved_by_id=current_user.id,
            approved_at=datetime.now(timezone.utc)
        )
        db.add(tx_out)

        # ورود ته‌شاخه به انبار
        if remnant_len > 0:
            remnant_qty = (remnant_weight / 1000.0) if is_ton else remnant_weight
            if remnant_qty <= 0:
                remnant_qty = mother_qty * (remnant_len / original_length)
            tx_in_remnant = StockTransaction(
                transaction_type=TransactionType.IN,
                transaction_source="CUTTING",
                product_id=product_id,
                warehouse_id=wh_id,
                quantity=round(remnant_qty, 3),
                secondary_quantity=1.0,
                secondary_uom='ته‌شاخه',
                unit_price=avg_cost,
                currency=wh_currency,
                exchange_rate=1.0,
                status=DocumentStatus.APPROVED,
                fiscal_year_id=fy_id,
                reference_document=f"ورود ته‌شاخه برش ({remnant_len:.1f}m) - دستور {cutting.order_number}",
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.now(timezone.utc)
            )
            db.add(tx_in_remnant)

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="CuttingOrder",
            entity_id=str(cutting.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت دستور برش {cutting.order_number} و صدور خودکار حواله خروج شاخه مادر و رسید ورود ته‌شاخه"
        )

        success_msg = f"Kesim emri {cutting.order_number} kaydedildi ve kalan kısım {destination} stoğuna aktarıldı" if is_tr else f"دستور برش {cutting.order_number} با موفقیت ثبت شد و ته‌شاخه به {destination} منتقل گردید"

        return RedirectResponse(
            url="/cutting?msg=" + quote(success_msg),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در ثبت دستور برش: {str(e)}")
