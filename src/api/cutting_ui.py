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
from src.domain_model.inventory_models import CuttingOrder, Product, Warehouse, StockTransaction, TransactionType
from src.domain_model.enums import CuttingStatus, DocumentStatus
from src.services.audit_service import AuditService
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(prefix="/cutting", tags=["Cutting & Remnants"])
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
        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="CuttingOrder",
            entity_id=str(cutting.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت دستور برش {cutting.order_number}: برش شاخه ۱۲ متری به {pieces_count} قطعه {cut_length} متری | باقیمانده: {remnant_len} متر ({destination})"
        )

        success_msg = f"Kesim emri {cutting.order_number} kaydedildi ve kalan kısım {destination} stoğuna aktarıldı" if is_tr else f"دستور برش {cutting.order_number} با موفقیت ثبت شد و ته‌شاخه به {destination} منتقل گردید"

        return RedirectResponse(
            url="/cutting?msg=" + quote(success_msg),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در ثبت دستور برش: {str(e)}")
