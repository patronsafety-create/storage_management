from typing import Optional
from urllib.parse import quote
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from src.infrastructure.database import get_db
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import (
    WeighbridgeTicket,
    Supplier,
    Customer,
    Product,
    Warehouse,
    StockTransaction,
    TransactionType
)
from src.domain_model.enums import WeighbridgeStatus, DocumentStatus
from src.services.audit_service import AuditService
from src.core.localization.regions import get_active_region, Region, localize_display_name
from src.core.localization.tr_rules import (
    validate_turkish_plate,
    format_turkish_plate,
    check_kgm_weight_limit
)

router = APIRouter(prefix="/weighbridge", tags=["Weighbridge Engine"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("", response_class=HTMLResponse)
async def list_weighbridge_tickets(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    status_filter: Optional[str] = Query(None),
    plate_search: Optional[str] = Query(None)
):
    """لیست و داشبورد نوبت‌ها و قبوض باسکول دیجیتال تریلی و ناوگان"""
    query = (
        db.query(WeighbridgeTicket)
        .options(
            joinedload(WeighbridgeTicket.supplier),
            joinedload(WeighbridgeTicket.customer),
            joinedload(WeighbridgeTicket.product),
            joinedload(WeighbridgeTicket.warehouse)
        )
        .order_by(WeighbridgeTicket.created_at.desc())
    )

    if status_filter:
        query = query.filter(WeighbridgeTicket.status == WeighbridgeStatus[status_filter])
    if plate_search:
        query = query.filter(WeighbridgeTicket.truck_plate.ilike(f"%{plate_search.strip()}%"))

    tickets = query.all()

    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    # شاخص‌های آماری باسکول
    total_trucks = len(tickets)
    in_yard = sum(1 for t in tickets if t.status == WeighbridgeStatus.FIRST_WEIGHING)
    completed_tickets = sum(1 for t in tickets if t.status == WeighbridgeStatus.COMPLETED)
    overweight_alerts = sum(1 for t in tickets if t.is_overweight)
    total_net_tonnage = sum(t.net_weight or 0.0 for t in tickets if t.status == WeighbridgeStatus.COMPLETED) / 1000.0

    return templates.TemplateResponse(
        request=request,
        name="weighbridge.html",
        context={
            "request": request,
            "tickets": tickets,
            "status_filter": status_filter,
            "plate_search": plate_search,
            "total_trucks": total_trucks,
            "in_yard": in_yard,
            "completed_tickets": completed_tickets,
            "overweight_alerts": overweight_alerts,
            "total_net_tonnage": total_net_tonnage,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/new", response_class=HTMLResponse)
async def new_weighbridge_form(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت نوبت توزین اول باسکول (ورود ناوگان به محوطه)"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    suppliers = db.query(Supplier).filter_by(is_active=True).all()
    customers = db.query(Customer).filter_by(is_active=True).all()
    products = db.query(Product).filter_by(is_active=True).all()
    warehouses = db.query(Warehouse).all()

    count = db.query(WeighbridgeTicket).count() + 1
    generated_ticket_number = f"WB-TR-{count:04d}" if is_tr else f"WB-1403-{count:04d}"

    return templates.TemplateResponse(
        request=request,
        name="weighbridge_form.html",
        context={
            "request": request,
            "generated_ticket_number": generated_ticket_number,
            "suppliers": suppliers,
            "customers": customers,
            "products": products,
            "warehouses": warehouses,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("", response_class=HTMLResponse)
async def create_weighbridge_ticket(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ticket_number: str = Form(...),
    truck_plate: str = Form(...),
    driver_name: str = Form(...),
    driver_phone: Optional[str] = Form(None),
    truck_type: str = Form("تریلی کفی ۱۸ چرخ"),
    weighing_mode: str = Form("INBOUND"), # INBOUND (ورود پر، خروج خالی) یا OUTBOUND (ورود خالی، خروج پر)
    initial_weight: float = Form(...),
    max_allowed_weight: float = Form(40000.0),
    product_id: int = Form(...),
    warehouse_id: int = Form(...),
    supplier_id: Optional[int] = Form(None),
    customer_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(None)
):
    """ثبت مرحله اول توزین تریلی بر روی باسکول"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    try:
        clean_plate = truck_plate.strip()
        if is_tr and validate_turkish_plate(clean_plate):
            clean_plate = format_turkish_plate(clean_plate)

        # کنترل اضافه تناژ راهداری (KGM در ترکیه یا سقف ورودی)
        if is_tr:
            is_kgm_over, kgm_limit, _ = check_kgm_weight_limit(initial_weight, truck_type)
            max_allowed_weight = kgm_limit
            is_over = is_kgm_over if weighing_mode == "INBOUND" else False
        else:
            is_over = (initial_weight > max_allowed_weight) if weighing_mode == "INBOUND" else False

        gross = initial_weight if weighing_mode == "INBOUND" else 0.0
        tare = initial_weight if weighing_mode == "OUTBOUND" else 0.0

        ticket = WeighbridgeTicket(
            ticket_number=ticket_number.strip(),
            truck_plate=clean_plate,
            driver_name=driver_name.strip(),
            driver_phone=driver_phone.strip() if driver_phone else None,
            truck_type=truck_type.strip(),
            product_id=product_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id if supplier_id and supplier_id > 0 else None,
            customer_id=customer_id if customer_id and customer_id > 0 else None,
            gross_weight=gross,
            tare_weight=tare,
            net_weight=0.0,
            max_allowed_weight=max_allowed_weight,
            is_overweight=is_over,
            status=WeighbridgeStatus.FIRST_WEIGHING,
            operator_name=current_user.full_name or current_user.username,
            notes=notes.strip() if notes else None
        )
        db.add(ticket)
        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="WeighbridgeTicket",
            entity_id=str(ticket.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"ثبت نوبت توزین اول باسکول {ticket.ticket_number} برای پلاک {ticket.truck_plate} با وزن اولیه {initial_weight} کیلوگرم"
        )

        success_msg = f"Kantar fişi {ticket.ticket_number} başarıyla kaydedildi" if is_tr else f"نوبت باسکول {ticket.ticket_number} با موفقیت ثبت شد"
        return RedirectResponse(
            url=f"/weighbridge?msg=" + quote(success_msg),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در ثبت نوبت باسکول: {str(e)}")


@router.get("/{ticket_id}/second", response_class=HTMLResponse)
async def second_weighing_form(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """فرم ثبت مرحله دوم توزین (توزین متقابل) و محاسبه خالص نهایی"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    ticket = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="قبض باسکول یافت نشد")

    return templates.TemplateResponse(
        request=request,
        name="weighbridge_second_form.html",
        context={
            "request": request,
            "ticket": ticket,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.post("/{ticket_id}/complete", response_class=HTMLResponse)
async def complete_second_weighing(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    second_weight: float = Form(...),
    auto_create_transaction: bool = Form(False)
):
    """ثبت توزین دوم، محاسبه وزن خالص و مختومه‌سازی نوبت باسکول"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    ticket = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="قبض باسکول یافت نشد")

    try:
        if ticket.gross_weight and ticket.gross_weight > 0:
            # توزین اول ناخالص بوده، توزین دوم تار (خالی) است
            ticket.tare_weight = second_weight
        else:
            # توزین اول تار بوده، توزین دوم ناخالص (پر) است
            ticket.gross_weight = second_weight

        ticket.net_weight = abs(ticket.gross_weight - ticket.tare_weight)
        ticket.status = WeighbridgeStatus.COMPLETED
        ticket.completed_at = datetime.now()

        # بررسی نهایی سقف تناژ پلیس‌راه یا KGM
        if is_tr:
            is_kgm_over, kgm_limit, _ = check_kgm_weight_limit(ticket.gross_weight, ticket.truck_type)
            ticket.max_allowed_weight = kgm_limit
            ticket.is_overweight = is_kgm_over
        else:
            if ticket.gross_weight > ticket.max_allowed_weight:
                ticket.is_overweight = True

        # صدور مستقیم سند انبار در صورت انتخاب کاربر
        if auto_create_transaction:
            tx_type = TransactionType.IN if ticket.supplier_id else TransactionType.OUT
            net_ton = ticket.net_weight / 1000.0 if ticket.product.uom == "تن" else ticket.net_weight
            tx = StockTransaction(
                transaction_type=tx_type,
                product_id=ticket.product_id,
                warehouse_id=ticket.warehouse_id,
                quantity=net_ton,
                supplier_id=ticket.supplier_id,
                customer_id=ticket.customer_id,
                reference_document=ticket.ticket_number,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id
            )
            db.add(tx)
            db.flush()
            ticket.stock_transaction_id = tx.id

        db.commit()

        AuditService.log(
            db, action="APPROVE", entity_name="WeighbridgeTicket",
            entity_id=str(ticket.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"تکمیل توزین دوم قبض {ticket.ticket_number} - وزن خالص: {ticket.net_weight} کیلوگرم"
        )

        return RedirectResponse(
            url=f"/weighbridge/{ticket.id}/print",
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در قطعی کردن توزین: {str(e)}")


@router.get("/{ticket_id}/print", response_class=HTMLResponse)
async def print_weighbridge_slip(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """برگه رسمی چاپ قبض باسکول با بارکد و گرافیک ناوگان و امضاها"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    ticket = (
        db.query(WeighbridgeTicket)
        .options(
            joinedload(WeighbridgeTicket.supplier),
            joinedload(WeighbridgeTicket.customer),
            joinedload(WeighbridgeTicket.product),
            joinedload(WeighbridgeTicket.warehouse)
        )
        .filter(WeighbridgeTicket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=404, detail="قبض باسکول یافت نشد")

    return templates.TemplateResponse(
        request=request,
        name="weighbridge_slip.html",
        context={
            "request": request,
            "ticket": ticket,
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )
