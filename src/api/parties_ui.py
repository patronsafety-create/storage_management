from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_

from src.core.dependencies import get_db, require_admin, get_current_user
from src.domain_model.inventory_models import Supplier, Customer, StockTransaction, TransactionType
from src.domain_model.auth_models import User

router = APIRouter(
    prefix="/master-data",
    tags=["Business Partners"]
)

templates = Jinja2Templates(directory="templates")


@router.get("/parties", response_class=HTMLResponse)
async def list_parties(
    request: Request,
    search: Optional[str] = Query(None),
    tab: Optional[str] = Query("suppliers"),
    msg: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مدیریت طرف‌های تجاری: تأمین‌کنندگان و مشتریان"""
    is_admin = any(role.name == "Admin" for role in current_user.roles)

    # کوئری تأمین‌کنندگان
    sup_query = db.query(Supplier)
    cust_query = db.query(Customer)

    if search and search.strip():
        term = f"%{search.strip()}%"
        sup_query = sup_query.filter(
            or_(
                Supplier.name.ilike(term),
                Supplier.code.ilike(term),
                Supplier.contact_person.ilike(term),
                Supplier.phone.ilike(term),
                Supplier.national_id.ilike(term)
            )
        )
        cust_query = cust_query.filter(
            or_(
                Customer.name.ilike(term),
                Customer.code.ilike(term),
                Customer.contact_person.ilike(term),
                Customer.phone.ilike(term),
                Customer.national_id.ilike(term)
            )
        )

    suppliers_raw = sup_query.order_by(Supplier.name).all()
    customers_raw = cust_query.order_by(Customer.name).all()

    # محاسبه گردش و آمار برای هر تأمین‌کننده
    suppliers = []
    for s in suppliers_raw:
        tx_count = db.query(StockTransaction).filter(StockTransaction.supplier_id == s.id).count()
        total_qty = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.supplier_id == s.id
        ).scalar() or 0.0
        total_value = db.query(func.coalesce(func.sum(StockTransaction.quantity * StockTransaction.unit_price), 0.0)).filter(
            StockTransaction.supplier_id == s.id
        ).scalar() or 0.0
        suppliers.append({
            "party": s,
            "tx_count": tx_count,
            "total_qty": total_qty,
            "total_value": total_value
        })

    # محاسبه گردش و آمار برای هر مشتری
    customers = []
    for c in customers_raw:
        tx_count = db.query(StockTransaction).filter(StockTransaction.customer_id == c.id).count()
        total_qty = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.customer_id == c.id
        ).scalar() or 0.0
        total_value = db.query(func.coalesce(func.sum(StockTransaction.quantity * StockTransaction.unit_price), 0.0)).filter(
            StockTransaction.customer_id == c.id
        ).scalar() or 0.0
        customers.append({
            "party": c,
            "tx_count": tx_count,
            "total_qty": total_qty,
            "total_value": total_value
        })

    stats = {
        "total_suppliers": db.query(Supplier).count(),
        "total_customers": db.query(Customer).count(),
        "total_inbound_txs": db.query(StockTransaction).filter(StockTransaction.supplier_id.isnot(None)).count(),
        "total_outbound_txs": db.query(StockTransaction).filter(StockTransaction.customer_id.isnot(None)).count(),
    }

    return templates.TemplateResponse(
        request=request,
        name="parties.html",
        context={
            "request": request,
            "user": current_user,
            "current_user": current_user,
            "is_admin": is_admin,
            "suppliers": suppliers,
            "customers": customers,
            "stats": stats,
            "active_tab": tab or "suppliers",
            "search": search or "",
            "msg": msg,
            "error": error
        }
    )


@router.post("/supplier")
async def create_supplier(
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ایجاد تأمین‌کننده جدید"""
    try:
        clean_name = name.strip()
        clean_code = code.strip().upper() if code and code.strip() else f"SUP-{db.query(Supplier).count() + 1:03d}"

        new_sup = Supplier(
            name=clean_name,
            code=clean_code,
            contact_person=contact_person.strip() if contact_person and contact_person.strip() else None,
            phone=phone.strip() if phone and phone.strip() else None,
            email=email.strip() if email and email.strip() else None,
            address=address.strip() if address and address.strip() else None,
            national_id=national_id.strip() if national_id and national_id.strip() else None,
            is_active=True
        )
        db.add(new_sup)
        db.commit()
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&msg={quote('تأمین‌کننده جدید با موفقیت ثبت شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote('نام تأمین‌کننده یا کد آن تکراری است')}",
            status_code=303
        )


@router.post("/supplier/{supplier_id}/edit")
async def edit_supplier(
    supplier_id: int,
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ویرایش اطلاعات تأمین‌کننده"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return RedirectResponse(url="/master-data/parties?tab=suppliers&error=" + quote("تأمین‌کننده یافت نشد"), status_code=303)

    try:
        supplier.name = name.strip()
        supplier.code = code.strip().upper() if code and code.strip() else supplier.code
        supplier.contact_person = contact_person.strip() if contact_person and contact_person.strip() else None
        supplier.phone = phone.strip() if phone and phone.strip() else None
        supplier.email = email.strip() if email and email.strip() else None
        supplier.address = address.strip() if address and address.strip() else None
        supplier.national_id = national_id.strip() if national_id and national_id.strip() else None
        db.commit()
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&msg={quote('مشخصات تأمین‌کننده با موفقیت به‌روزرسانی شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote('تداخل در نام یا کد تأمین‌کننده')}",
            status_code=303
        )


@router.post("/supplier/{supplier_id}/toggle-status")
async def toggle_supplier_status(
    supplier_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """تغییر وضعیت فعال/غیرفعال تأمین‌کننده"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if supplier:
        supplier.is_active = not supplier.is_active
        db.commit()
        state = "فعال" if supplier.is_active else "غیرفعال"
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&msg={quote(f'وضعیت تأمین‌کننده به {state} تغییر یافت')}",
            status_code=303
        )
    return RedirectResponse(url="/master-data/parties?tab=suppliers", status_code=303)


@router.post("/customer")
async def create_customer(
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    credit_limit: Optional[float] = Form(0.0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ایجاد مشتری جدید"""
    try:
        clean_name = name.strip()
        clean_code = code.strip().upper() if code and code.strip() else f"CUST-{db.query(Customer).count() + 1:03d}"

        new_cust = Customer(
            name=clean_name,
            code=clean_code,
            contact_person=contact_person.strip() if contact_person and contact_person.strip() else None,
            phone=phone.strip() if phone and phone.strip() else None,
            email=email.strip() if email and email.strip() else None,
            address=address.strip() if address and address.strip() else None,
            national_id=national_id.strip() if national_id and national_id.strip() else None,
            credit_limit=credit_limit or 0.0,
            is_active=True
        )
        db.add(new_cust)
        db.commit()
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&msg={quote('مشتری جدید با موفقیت ثبت شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote('نام مشتری یا کد آن تکراری است')}",
            status_code=303
        )


@router.post("/customer/{customer_id}/edit")
async def edit_customer(
    customer_id: int,
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    credit_limit: Optional[float] = Form(0.0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ویرایش اطلاعات مشتری"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return RedirectResponse(url="/master-data/parties?tab=customers&error=" + quote("مشتری یافت نشد"), status_code=303)

    try:
        customer.name = name.strip()
        customer.code = code.strip().upper() if code and code.strip() else customer.code
        customer.contact_person = contact_person.strip() if contact_person and contact_person.strip() else None
        customer.phone = phone.strip() if phone and phone.strip() else None
        customer.email = email.strip() if email and email.strip() else None
        customer.address = address.strip() if address and address.strip() else None
        customer.national_id = national_id.strip() if national_id and national_id.strip() else None
        customer.credit_limit = credit_limit or 0.0
        db.commit()
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&msg={quote('مشخصات مشتری با موفقیت به‌روزرسانی شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote('تداخل در نام یا کد مشتری')}",
            status_code=303
        )


@router.post("/customer/{customer_id}/toggle-status")
async def toggle_customer_status(
    customer_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """تغییر وضعیت فعال/غیرفعال مشتری"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer:
        customer.is_active = not customer.is_active
        db.commit()
        state = "فعال" if customer.is_active else "غیرفعال"
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&msg={quote(f'وضعیت مشتری به {state} تغییر یافت')}",
            status_code=303
        )
    return RedirectResponse(url="/master-data/parties?tab=customers", status_code=303)
