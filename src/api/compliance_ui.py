import io
import csv
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from src.infrastructure.database import get_db
from src.core.dependencies import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import Product, StockTransaction, Warehouse
from src.core.localization.regions import get_active_region, Region, localize_display_name

router = APIRouter(prefix="/compliance", tags=["Trade & Regulatory Compliance"])
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("", response_class=HTMLResponse)
async def compliance_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """داشبورد انطباق با سامانه‌های دولتی (سامانه جامع تجارت ntsw.ir و سامانه جامع انبارها nwms.ir)"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    products = db.query(Product).filter_by(is_active=True).all()
    transactions = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer)
        )
        .order_by(StockTransaction.created_at.desc())
        .limit(100)
        .all()
    )

    products_with_irc = sum(1 for p in products if (p.gtip_code if is_tr else p.irc_code))
    tx_with_waybill = sum(1 for t in transactions if t.waybill_number or t.tracking_code)

    return templates.TemplateResponse(
        request=request,
        name="compliance.html",
        context={
            "request": request,
            "products": products,
            "transactions": transactions,
            "products_with_irc": products_with_irc,
            "total_products": len(products),
            "tx_with_waybill": tx_with_waybill,
            "total_transactions": len(transactions),
            "user": current_user,
            "active_region": active_region,
            "is_tr": is_tr
        }
    )


@router.get("/export/ntsw")
async def export_ntsw_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """خروجی استاندارد منطبق با الگوی بارگذاری دسته‌ای در سامانه جامع تجارت (ntsw.ir) با انکودینگ UTF-8 BOM جهت باز شدن در اکسل"""
    txs = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer)
        )
        .order_by(StockTransaction.created_at.desc())
        .all()
    )

    fieldnames = [
        "شناسه یکتای سند",
        "نوع سند تجارت",
        "شناسه کالا (IRC)",
        "کد بین‌المللی تعرفه (HS Code)",
        "نام کالا",
        "واحد سنجش",
        "مقدار خالص",
        "شماره پارت / ذوب",
        "نام انبار مبدأ/مقصد",
        "نام طرف حساب تجاری",
        "شناسه ملی / کد اقتصادی طرف حساب",
        "شماره بارنامه برخط",
        "کد رهگیری جامع تجارت",
        "تاریخ ثبت سند",
        "وضعیت سند"
    ]

    output = io.StringIO()
    # Write UTF-8 BOM so Excel opens it with Persian characters automatically
    output.write('\ufeff')
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for t in txs:
        party_name = t.supplier.name if t.supplier else (t.customer.name if t.customer else "آزاد")
        party_national_id = t.supplier.national_id if t.supplier else (t.customer.national_id if t.customer else "")
        op_type = "ورود به انبار (رسید)" if t.transaction_type.value == "IN" else "خروج از انبار (حواله)"

        writer.writerow({
            "شناسه یکتای سند": t.id,
            "نوع سند تجارت": op_type,
            "شناسه کالا (IRC)": t.product.irc_code or ("۲۸۰۰۰۰۰" + str(t.product.id).zfill(6) if t.product else ""),
            "کد بین‌المللی تعرفه (HS Code)": (t.product.hs_code or "۷۲۱۴۲۰۰۰") if t.product else "",
            "نام کالا": t.product.name if t.product else "",
            "واحد سنجش": t.product.uom if t.product else "",
            "مقدار خالص": t.quantity,
            "شماره پارت / ذوب": t.heat_number or t.batch_number or "---",
            "نام انبار مبدأ/مقصد": t.warehouse.name if t.warehouse else "",
            "نام طرف حساب تجاری": party_name,
            "شناسه ملی / کد اقتصادی طرف حساب": party_national_id,
            "شماره بارنامه برخط": t.waybill_number or "---",
            "کد رهگیری جامع تجارت": t.tracking_code or "---",
            "تاریخ ثبت سند": t.created_at.strftime('%Y/%m/%d') if t.created_at else "",
            "وضعیت سند": "تأیید نهایی و رسمی"
        })

    output_bytes = io.BytesIO(output.getvalue().encode('utf-8-sig'))
    headers = {
        'Content-Disposition': 'attachment; filename="NTSW_Trade_Export.csv"'
    }
    return StreamingResponse(
        output_bytes,
        media_type='text/csv; charset=utf-8-sig',
        headers=headers
    )
