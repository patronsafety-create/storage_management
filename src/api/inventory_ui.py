from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# تعریف روتر اختصاصی برای ماژول انبار
router = APIRouter(prefix="/inventory", tags=["Inventory UI"])
templates = Jinja2Templates(directory="templates")

@router.get("/transaction", response_class=HTMLResponse)
async def get_transaction_form(request: Request):
    """
    رندر فرم ثبت رسید و حواله.
    در این مرحله داده‌ها به صورت تستی (Mock) ارسال می‌شوند تا پایداری فرم تأیید شود.
    پس از تأیید، این داده‌ها مستقیماً از جداول SQLAlchemy خوانده خواهند شد.
    """
    mock_products = [
        {"id": 1, "name": "کابل شبکه CAT6 - حلقه ۵۰۰ متری"},
        {"id": 2, "name": "سوئیچ ۲۴ پورت سیسکو"},
        {"id": 3, "name": "سرور HP DL380 G10"}
    ]
    
    mock_warehouses = [
        {"id": 1, "name": "انبار قطعات (تهران)"},
        {"id": 2, "name": "انبار مرکزی (کرج)"}
    ]

    return templates.TemplateResponse(
        request=request, 
        name="transaction_form.html", 
        context={
            "request": request,
            "products": mock_products,
            "warehouses": mock_warehouses
        }
    )