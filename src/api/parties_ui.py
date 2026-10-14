from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_

from src.core.dependencies import get_db, require_admin, get_current_user
from src.core.localization.regions import get_active_region, Region, localize_display_name
from src.core.localization.tr_rules import validate_turkish_party_data
from src.domain_model.inventory_models import (
    Supplier, Customer, StockTransaction, TransactionType,
    PurchaseOrder, WeighbridgeTicket
)
from src.domain_model.auth_models import User

router = APIRouter(
    prefix="/master-data",
    tags=["Business Partners"]
)

templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("/parties", response_class=HTMLResponse)
async def list_parties(
    request: Request,
    search: Optional[str] = Query(None),
    status: Optional[str] = Query("all"),
    tab: Optional[str] = Query("suppliers"),
    msg: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """مدیریت طرف‌های تجاری: تأمین‌کنندگان و مشتریان"""
    is_admin = any(role.name == "Admin" for role in current_user.roles)
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    # کوئری تأمین‌کنندگان و مشتریان
    sup_query = db.query(Supplier)
    cust_query = db.query(Customer)

    # فیلتر وضعیت فعال / غیرفعال
    if status == "active":
        sup_query = sup_query.filter(Supplier.is_active == True)
        cust_query = cust_query.filter(Customer.is_active == True)
    elif status == "inactive":
        sup_query = sup_query.filter(Supplier.is_active == False)
        cust_query = cust_query.filter(Customer.is_active == False)

    if search and search.strip():
        term = f"%{search.strip()}%"
        sup_query = sup_query.filter(
            or_(
                Supplier.name.ilike(term),
                Supplier.code.ilike(term),
                Supplier.contact_person.ilike(term),
                Supplier.phone.ilike(term),
                Supplier.national_id.ilike(term),
                Supplier.vkn.ilike(term),
                Supplier.tax_office.ilike(term)
            )
        )
        cust_query = cust_query.filter(
            or_(
                Customer.name.ilike(term),
                Customer.code.ilike(term),
                Customer.contact_person.ilike(term),
                Customer.phone.ilike(term),
                Customer.national_id.ilike(term),
                Customer.vkn.ilike(term),
                Customer.tax_office.ilike(term)
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
            "status_filter": status or "all",
            "msg": msg,
            "error": error,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


def to_english_digits(text: Optional[str]) -> str:
    """تبدیل کلیه ارقام فارسی و عربی به ارقام انگلیسی"""
    if not text:
        return ""
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    arabic_digits = "٠١٢٣٤٥٦٧٨٩"
    result = str(text)
    for i, d in enumerate(persian_digits):
        result = result.replace(d, str(i))
    for i, d in enumerate(arabic_digits):
        result = result.replace(d, str(i))
    return result


def is_valid_iranian_national_code(code: str) -> bool:
    """اعتبارسنجی الگوریتم ۱۰ رقمی کد ملی اشخاص حقیقی با رقم کنترل"""
    clean = to_english_digits(code).replace("-", "").strip()
    if len(clean) != 10 or not clean.isdigit():
        return False
    # کدهای با ارقام تماماً یکسان نامعتبرند
    if len(set(clean)) == 1:
        return False
    check_digit = int(clean[9])
    total_sum = sum(int(clean[i]) * (10 - i) for i in range(9))
    remainder = total_sum % 11
    if remainder < 2:
        return check_digit == remainder
    return check_digit == (11 - remainder)


def validate_party_data(
    name: str,
    phone: Optional[str],
    national_id: Optional[str],
    party_type_label: str = "طرف تجاری"
) -> tuple[Optional[str], str, Optional[str], Optional[str]]:
    """
    اعتبارسنجی جامع مشخصات طرف تجاری:
    1. نام: حداقل ۳ کاراکتر، دارای حروف، جلوگیری از ورود صرفاً عدد
    2. شماره تماس: الزامی، دقیقاً ۱۱ رقم، آغاز با 09 یا 0
    3. کد ملی / شناسه اقتصادی: در صورت ورود، ۱۰ رقم معتبر یا ۱۱ رقم حقوقی
    """
    clean_name = name.strip()
    clean_phone = to_english_digits(phone).replace("-", "").replace(" ", "").strip() if phone else ""
    clean_nid = to_english_digits(national_id).replace("-", "").replace(" ", "").strip() if national_id else None

    # ۱. اعتبارسنجی نام
    if len(clean_name) < 3:
        return (f"نام {party_type_label} باید حداقل ۳ کاراکتر باشد.", clean_name, clean_phone, clean_nid)

    # جلوگیری از ورود صرفاً عدد در نام
    numeric_test = to_english_digits(clean_name).replace(" ", "").replace("-", "")
    if numeric_test.isdigit():
        return (f"نام {party_type_label} نمی‌تواند صرفاً از اعداد تشکیل شود. لطفاً نام معتبر شخص یا شرکت را وارد نمایید.", clean_name, clean_phone, clean_nid)

    # نام باید حداقل دارای یک حرف فارسی یا انگلیسی باشد
    has_letter = any(c.isalpha() or '\u0600' <= c <= '\u06FF' for c in clean_name)
    if not has_letter:
        return (f"نام {party_type_label} باید شامل حروف معتبر باشد.", clean_name, clean_phone, clean_nid)

    # ۲. اعتبارسنجی شماره تماس
    if not clean_phone:
        return (f"وارد کردن شماره تماس / همراه برای {party_type_label} الزامی است.", clean_name, clean_phone, clean_nid)

    if not clean_phone.isdigit() or len(clean_phone) != 11 or not (clean_phone.startswith("09") or clean_phone.startswith("0")):
        return ("شماره تماس وارد شده نامعتبر است. شماره همراه باید ۱۱ رقم بوده و با ۰۹ شروع شود (مثلاً ۰۹۱۲۳۴۵۶۷۸۹).", clean_name, clean_phone, clean_nid)

    # ۳. اعتبارسنجی شناسه ملی / کد اقتصادی
    if clean_nid:
        if not clean_nid.isdigit():
            return ("شناسه ملی یا کد اقتصادی باید صرفاً از ارقام تشکیل شده باشد.", clean_name, clean_phone, clean_nid)
        if len(clean_nid) not in (10, 11):
            return ("شناسه ملی / کد اقتصادی باید ۱۰ رقم (اشخاص حقیقی) یا ۱۱ رقم (اشخاص حقوقی) باشد.", clean_name, clean_phone, clean_nid)
        if len(clean_nid) == 10 and not is_valid_iranian_national_code(clean_nid):
            return ("کد ملی ۱۰ رقمی وارد شده نامعتبر است (رقم کنترل چک‌سام ناصحیح است).", clean_name, clean_phone, clean_nid)

    return (None, clean_name, clean_phone, clean_nid)


@router.post("/supplier")
async def create_supplier(
    request: Request,
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    country_code: Optional[str] = Form("IR"),
    vkn: Optional[str] = Form(None),
    tax_office: Optional[str] = Form(None),
    mersis_no: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ایجاد تأمین‌کننده جدید با پشتیبانی از سیستم مالیاتی ایران و ترکیه"""
    active_region = get_active_region(request)
    effective_country = (country_code or active_region.code or "IR").upper()

    if effective_country == "TR":
        tax_num = (vkn or national_id or "").strip()
        err, clean_name, clean_phone, clean_tax_num = validate_turkish_party_data(
            name, phone, tax_num if tax_num else None, "Tedarikçi"
        )
        clean_nid = None
        clean_vkn = clean_tax_num
    else:
        err, clean_name, clean_phone, clean_nid = validate_party_data(name, phone, national_id, "تأمین‌کننده")
        clean_vkn = vkn.strip() if vkn else None

    if err:
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote(err)}",
            status_code=303
        )

    try:
        clean_code = code.strip().upper() if code and code.strip() else f"SUP-{db.query(Supplier).count() + 1:03d}"

        new_sup = Supplier(
            name=clean_name,
            code=clean_code,
            contact_person=contact_person.strip() if contact_person and contact_person.strip() else None,
            phone=clean_phone,
            email=email.strip() if email and email.strip() else None,
            address=address.strip() if address and address.strip() else None,
            national_id=clean_nid,
            country_code=effective_country,
            vkn=clean_vkn,
            tax_office=tax_office.strip() if tax_office and tax_office.strip() else None,
            mersis_no=mersis_no.strip() if mersis_no and mersis_no.strip() else None,
            is_active=True
        )
        db.add(new_sup)
        db.commit()
        msg = "Tedarikçi başarıyla kaydedildi" if effective_country == "TR" else "تأمین‌کننده جدید با موفقیت ثبت شد"
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&msg={quote(msg)}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        err_msg = "Tedarikçi adı veya kodu zaten mevcut" if effective_country == "TR" else "نام تأمین‌کننده یا کد آن تکراری است"
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote(err_msg)}",
            status_code=303
        )


@router.post("/supplier/{supplier_id}/edit")
async def edit_supplier(
    supplier_id: int,
    request: Request,
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    country_code: Optional[str] = Form("IR"),
    vkn: Optional[str] = Form(None),
    tax_office: Optional[str] = Form(None),
    mersis_no: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ویرایش اطلاعات تأمین‌کننده با پشتیبانی از سیستم مالیاتی ایران و ترکیه"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return RedirectResponse(url="/master-data/parties?tab=suppliers&error=" + quote("تأمین‌کننده یافت نشد"), status_code=303)

    active_region = get_active_region(request)
    effective_country = (country_code or supplier.country_code or active_region.code or "IR").upper()

    if effective_country == "TR":
        tax_num = (vkn or national_id or "").strip()
        err, clean_name, clean_phone, clean_tax_num = validate_turkish_party_data(
            name, phone, tax_num if tax_num else None, "Tedarikçi"
        )
        clean_nid = supplier.national_id if not national_id else national_id.strip()
        clean_vkn = clean_tax_num
    else:
        err, clean_name, clean_phone, clean_nid = validate_party_data(name, phone, national_id, "تأمین‌کننده")
        clean_vkn = vkn.strip() if vkn else supplier.vkn

    if err:
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote(err)}",
            status_code=303
        )

    try:
        supplier.name = clean_name
        supplier.code = code.strip().upper() if code and code.strip() else supplier.code
        supplier.contact_person = contact_person.strip() if contact_person and contact_person.strip() else None
        supplier.phone = clean_phone
        supplier.email = email.strip() if email and email.strip() else None
        supplier.address = address.strip() if address and address.strip() else None
        supplier.national_id = clean_nid
        supplier.country_code = effective_country
        supplier.vkn = clean_vkn
        supplier.tax_office = tax_office.strip() if tax_office and tax_office.strip() else None
        supplier.mersis_no = mersis_no.strip() if mersis_no and mersis_no.strip() else None
        db.commit()
        msg = "Tedarikçi bilgileri başarıyla güncellendi" if effective_country == "TR" else "مشخصات تأمین‌کننده با موفقیت به‌روزرسانی شد"
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&msg={quote(msg)}",
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


@router.post("/supplier/{supplier_id}/delete")
async def delete_supplier(
    supplier_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """حذف قطعی تأمین‌کننده در صورت عدم وجود گردش یا اسناد مرتبط"""
    supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not supplier:
        return RedirectResponse(
            url="/master-data/parties?tab=suppliers&error=" + quote("تأمین‌کننده مورد نظر یافت نشد."),
            status_code=303
        )

    tx_count = db.query(StockTransaction).filter(StockTransaction.supplier_id == supplier_id).count()
    po_count = db.query(PurchaseOrder).filter(PurchaseOrder.supplier_id == supplier_id).count()
    wb_count = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.supplier_id == supplier_id).count()

    if tx_count > 0 or po_count > 0 or wb_count > 0:
        reasons = []
        if tx_count > 0:
            reasons.append(f"{tx_count} سند ورود/رسید انبار")
        if po_count > 0:
            reasons.append(f"{po_count} سفارش خرید")
        if wb_count > 0:
            reasons.append(f"{wb_count} قبض باسکول")
        reason_str = "، ".join(reasons)
        err_msg = (
            f"امکان حذف قطعی تأمین‌کننده «{supplier.name}» وجود ندارد؛ زیرا دارای گردش اسناد در سامانه است ({reason_str}). "
            "جهت حفظ یکپارچگی دفاتر مالی و کاردکس انبار، لطفاً وضعیت آن را به «غیرفعال» تغییر دهید تا در لیست‌های روزانه پنهان شود."
        )
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote(err_msg)}",
            status_code=303
        )

    try:
        sup_name = supplier.name
        db.delete(supplier)
        db.commit()
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&msg={quote(f'تأمین‌کننده «{sup_name}» با موفقیت به صورت قطعی حذف شد.')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/parties?tab=suppliers&error={quote('خطا در حذف: این طرف تجاری در سایر بخش‌های سیستم دارای وابستگی است.')}",
            status_code=303
        )



@router.post("/customer")
async def create_customer(
    request: Request,
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    country_code: Optional[str] = Form("IR"),
    vkn: Optional[str] = Form(None),
    tax_office: Optional[str] = Form(None),
    mersis_no: Optional[str] = Form(None),
    credit_limit: Optional[float] = Form(0.0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ایجاد مشتری جدید با پشتیبانی از سیستم مالیاتی ایران و ترکیه"""
    active_region = get_active_region(request)
    effective_country = (country_code or active_region.code or "IR").upper()

    if effective_country == "TR":
        tax_num = (vkn or national_id or "").strip()
        err, clean_name, clean_phone, clean_tax_num = validate_turkish_party_data(
            name, phone, tax_num if tax_num else None, "Müşteri"
        )
        clean_nid = None
        clean_vkn = clean_tax_num
    else:
        err, clean_name, clean_phone, clean_nid = validate_party_data(name, phone, national_id, "مشتری")
        clean_vkn = vkn.strip() if vkn else None

    if err:
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote(err)}",
            status_code=303
        )

    try:
        clean_code = code.strip().upper() if code and code.strip() else f"CUST-{db.query(Customer).count() + 1:03d}"

        new_cust = Customer(
            name=clean_name,
            code=clean_code,
            contact_person=contact_person.strip() if contact_person and contact_person.strip() else None,
            phone=clean_phone,
            email=email.strip() if email and email.strip() else None,
            address=address.strip() if address and address.strip() else None,
            national_id=clean_nid,
            country_code=effective_country,
            vkn=clean_vkn,
            tax_office=tax_office.strip() if tax_office and tax_office.strip() else None,
            mersis_no=mersis_no.strip() if mersis_no and mersis_no.strip() else None,
            credit_limit=credit_limit or 0.0,
            is_active=True
        )
        db.add(new_cust)
        db.commit()
        msg = "Müşteri başarıyla kaydedildi" if effective_country == "TR" else "مشتری جدید با موفقیت ثبت شد"
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&msg={quote(msg)}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        err_msg = "Müşteri adı veya kodu zaten mevcut" if effective_country == "TR" else "نام مشتری یا کد آن تکراری است"
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote(err_msg)}",
            status_code=303
        )


@router.post("/customer/{customer_id}/edit")
async def edit_customer(
    customer_id: int,
    request: Request,
    name: str = Form(...),
    code: Optional[str] = Form(None),
    contact_person: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    national_id: Optional[str] = Form(None),
    country_code: Optional[str] = Form("IR"),
    vkn: Optional[str] = Form(None),
    tax_office: Optional[str] = Form(None),
    mersis_no: Optional[str] = Form(None),
    credit_limit: Optional[float] = Form(0.0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ویرایش اطلاعات مشتری با پشتیبانی از سیستم مالیاتی ایران و ترکیه"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return RedirectResponse(url="/master-data/parties?tab=customers&error=" + quote("مشتری یافت نشد"), status_code=303)

    active_region = get_active_region(request)
    effective_country = (country_code or customer.country_code or active_region.code or "IR").upper()

    if effective_country == "TR":
        tax_num = (vkn or national_id or "").strip()
        err, clean_name, clean_phone, clean_tax_num = validate_turkish_party_data(
            name, phone, tax_num if tax_num else None, "Müşteri"
        )
        clean_nid = customer.national_id if not national_id else national_id.strip()
        clean_vkn = clean_tax_num
    else:
        err, clean_name, clean_phone, clean_nid = validate_party_data(name, phone, national_id, "مشتری")
        clean_vkn = vkn.strip() if vkn else customer.vkn

    if err:
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote(err)}",
            status_code=303
        )

    try:
        customer.name = clean_name
        customer.code = code.strip().upper() if code and code.strip() else customer.code
        customer.contact_person = contact_person.strip() if contact_person and contact_person.strip() else None
        customer.phone = clean_phone
        customer.email = email.strip() if email and email.strip() else None
        customer.address = address.strip() if address and address.strip() else None
        customer.national_id = clean_nid
        customer.country_code = effective_country
        customer.vkn = clean_vkn
        customer.tax_office = tax_office.strip() if tax_office and tax_office.strip() else None
        customer.mersis_no = mersis_no.strip() if mersis_no and mersis_no.strip() else None
        customer.credit_limit = credit_limit or 0.0
        db.commit()
        msg = "Müşteri bilgileri başarıyla güncellendi" if effective_country == "TR" else "مشخصات مشتری با موفقیت به‌روزرسانی شد"
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&msg={quote(msg)}",
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


@router.post("/customer/{customer_id}/delete")
async def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """حذف قطعی مشتری در صورت عدم وجود گردش یا اسناد مرتبط"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return RedirectResponse(
            url="/master-data/parties?tab=customers&error=" + quote("مشتری مورد نظر یافت نشد."),
            status_code=303
        )

    tx_count = db.query(StockTransaction).filter(StockTransaction.customer_id == customer_id).count()
    wb_count = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.customer_id == customer_id).count()

    if tx_count > 0 or wb_count > 0:
        reasons = []
        if tx_count > 0:
            reasons.append(f"{tx_count} سند حواله/خروج انبار")
        if wb_count > 0:
            reasons.append(f"{wb_count} قبض باسکول")
        reason_str = "، ".join(reasons)
        err_msg = (
            f"امکان حذف قطعی مشتری «{customer.name}» وجود ندارد؛ زیرا دارای سوابق در سیستم است ({reason_str}). "
            "جهت جلوگیری از مخدوش شدن دفاتر مالی و اسناد رهگیری، لطفاً مشتری را «غیرفعال» کنید تا در دید روزانه قرار نگیرد."
        )
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote(err_msg)}",
            status_code=303
        )

    try:
        cust_name = customer.name
        db.delete(customer)
        db.commit()
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&msg={quote(f'مشتری «{cust_name}» با موفقیت به صورت قطعی حذف شد.')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/parties?tab=customers&error={quote('خطا در حذف: این طرف تجاری در سایر بخش‌های سیستم دارای وابستگی است.')}",
            status_code=303
        )

