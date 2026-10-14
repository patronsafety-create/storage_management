import re
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, Form, Request, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func, or_

from src.core.dependencies import get_db, require_admin, get_current_user
from src.domain_model.inventory_models import Product, Warehouse, ProductCategory
from src.domain_model.auth_models import User
from src.services.inventory_service import InventoryService

router = APIRouter(
    prefix="/master-data",
    tags=["Master Data"]
)

templates = Jinja2Templates(directory="templates")


@router.get("/products", response_class=HTMLResponse)
async def list_products(
    request: Request,
    search: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    brand: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    msg: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """کاتالوگ جامع کالاها و مدیریت تعاریف پایه صنعتی"""
    is_admin = any(role.name == "Admin" for role in current_user.roles)

    query = db.query(Product).options(joinedload(Product.category))

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.sku.ilike(term),
                Product.brand.ilike(term),
                Product.size.ilike(term),
                Product.grade.ilike(term),
                Product.standard.ilike(term),
                Product.gtip_code.ilike(term),
                Product.tse_standard.ilike(term)
            )
        )

    if category_id:
        query = query.filter(Product.category_id == category_id)

    if brand and brand.strip():
        query = query.filter(Product.brand == brand.strip())

    if status == "active":
        query = query.filter(Product.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(Product.is_active.is_(False))

    products = query.order_by(Product.name).all()

    # استخراج دسته‌بندی‌ها و برندهای یکتا برای فیلتر
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()
    brands_query = db.query(Product.brand).filter(Product.brand.isnot(None), Product.brand != "").distinct().all()
    available_brands = [b[0] for b in brands_query if b[0]]

    # محاسبه موجودی لحظه‌ای و وضعیت هشدار برای هر کالا
    product_data = []
    low_stock_count = 0
    for p in products:
        stock = InventoryService.get_total_stock_all_warehouses(db, p.id)
        is_low = (p.reorder_point or 0.0) > 0 and stock <= (p.reorder_point or 0.0)
        if is_low:
            low_stock_count += 1
        product_data.append({
            "product": p,
            "total_stock": stock,
            "is_low": is_low
        })

    # آمارهای کلان کاتالوگ
    total_products = db.query(Product).count()
    total_categories = db.query(ProductCategory).count()
    total_active_brands = len(available_brands)

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "request": request,
            "user": current_user,
            "current_user": current_user,
            "is_admin": is_admin,
            "products_data": product_data,
            "categories": categories,
            "available_brands": available_brands,
            "search": search or "",
            "selected_category_id": category_id,
            "selected_brand": brand or "",
            "selected_status": status or "",
            "msg": msg,
            "error": error,
            "stats": {
                "total_products": total_products,
                "total_categories": total_categories,
                "total_brands": total_active_brands,
                "low_stock_count": low_stock_count
            }
        }
    )


@router.post("/product")
async def create_product(
    name: str = Form(...),
    uom: str = Form(...),
    sku: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    brand: Optional[str] = Form(None),
    size: Optional[str] = Form(None),
    length: Optional[float] = Form(None),
    thickness: Optional[float] = Form(None),
    grade: Optional[str] = Form(None),
    standard: Optional[str] = Form(None),
    gtip_code: Optional[str] = Form(None),
    tse_standard: Optional[str] = Form(None),
    min_stock: Optional[float] = Form(0.0),
    max_stock: Optional[float] = Form(0.0),
    reorder_point: Optional[float] = Form(0.0),
    description: Optional[str] = Form(None),
    return_to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ایجاد کالای جدید با مشخصات متالورژی و صنعتی"""
    try:
        clean_name = name.strip()
        clean_sku = sku.strip() if sku and sku.strip() else None

        # تولید خودکار SKU در صورت خالی بودن
        if not clean_sku:
            clean_sku = f"SKU-{re.sub(r'[^a-zA-Z0-9]', '', clean_name)[:8].upper()}-{db.query(Product).count() + 1:04d}"

        new_product = Product(
            name=clean_name,
            uom=uom.strip(),
            sku=clean_sku,
            category_id=category_id if category_id and category_id > 0 else None,
            brand=brand.strip() if brand and brand.strip() else None,
            size=size.strip() if size and size.strip() else None,
            length=length,
            thickness=thickness,
            grade=grade.strip() if grade and grade.strip() else None,
            standard=standard.strip() if standard and standard.strip() else None,
            gtip_code=gtip_code.strip() if gtip_code and gtip_code.strip() else None,
            tse_standard=tse_standard.strip() if tse_standard and tse_standard.strip() else None,
            min_stock=min_stock or 0.0,
            max_stock=max_stock or 0.0,
            reorder_point=reorder_point or 0.0,
            description=description.strip() if description and description.strip() else None,
            is_active=True
        )
        db.add(new_product)
        db.commit()

        target_url = return_to if return_to else "/master-data/products"
        return RedirectResponse(
            url=f"{target_url}?msg={quote('کالای جدید با موفقیت ثبت شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        target_url = return_to if return_to else "/master-data/products"
        return RedirectResponse(
            url=f"{target_url}?error={quote('نام کالا یا کد SKU تکراری است')}",
            status_code=303
        )


@router.post("/product/{product_id}/edit")
async def edit_product(
    product_id: int,
    name: str = Form(...),
    uom: str = Form(...),
    sku: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    brand: Optional[str] = Form(None),
    size: Optional[str] = Form(None),
    length: Optional[float] = Form(None),
    thickness: Optional[float] = Form(None),
    grade: Optional[str] = Form(None),
    standard: Optional[str] = Form(None),
    gtip_code: Optional[str] = Form(None),
    tse_standard: Optional[str] = Form(None),
    min_stock: Optional[float] = Form(0.0),
    max_stock: Optional[float] = Form(0.0),
    reorder_point: Optional[float] = Form(0.0),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ویرایش اطلاعات فنی و انبارداری کالا"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return RedirectResponse(
            url=f"/master-data/products?error={quote('کالای مورد نظر یافت نشد')}",
            status_code=303
        )

    try:
        product.name = name.strip()
        product.uom = uom.strip()
        product.sku = sku.strip() if sku and sku.strip() else product.sku
        product.category_id = category_id if category_id and category_id > 0 else None
        product.brand = brand.strip() if brand and brand.strip() else None
        product.size = size.strip() if size and size.strip() else None
        product.length = length
        product.thickness = thickness
        product.grade = grade.strip() if grade and grade.strip() else None
        product.standard = standard.strip() if standard and standard.strip() else None
        product.gtip_code = gtip_code.strip() if gtip_code and gtip_code.strip() else None
        product.tse_standard = tse_standard.strip() if tse_standard and tse_standard.strip() else None
        product.min_stock = min_stock or 0.0
        product.max_stock = max_stock or 0.0
        product.reorder_point = reorder_point or 0.0
        product.description = description.strip() if description and description.strip() else None

        db.commit()
        return RedirectResponse(
            url=f"/master-data/products?msg={quote('مشخصات کالا با موفقیت به‌روزرسانی شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        return RedirectResponse(
            url=f"/master-data/products?error={quote('نام یا کد SKU با کالای دیگری تداخل دارد')}",
            status_code=303
        )


@router.post("/product/{product_id}/toggle-status")
async def toggle_product_status(
    product_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """فعال / غیرفعال‌سازی کالا"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.is_active = not product.is_active
        db.commit()
        state_text = "فعال" if product.is_active else "غیرفعال"
        return RedirectResponse(
            url=f"/master-data/products?msg={quote(f'وضعیت کالا به {state_text} تغییر یافت')}",
            status_code=303
        )
    return RedirectResponse(url="/master-data/products", status_code=303)


@router.post("/category")
async def create_category(
    name: str = Form(...),
    code: Optional[str] = Form(None),
    parent_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    return_to: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """ایجاد گروه یا رده کالای جدید"""
    try:
        clean_code = code.strip().upper() if code and code.strip() else None
        new_cat = ProductCategory(
            name=name.strip(),
            code=clean_code,
            parent_id=parent_id if parent_id and parent_id > 0 else None,
            description=description.strip() if description and description.strip() else None
        )
        db.add(new_cat)
        db.commit()

        target_url = return_to if return_to else "/master-data/products"
        return RedirectResponse(
            url=f"{target_url}?msg={quote('دسته‌بندی جدید با موفقیت ایجاد شد')}",
            status_code=303
        )
    except IntegrityError:
        db.rollback()
        target_url = return_to if return_to else "/master-data/products"
        return RedirectResponse(
            url=f"{target_url}?error={quote('این دسته‌بندی یا کد رده از قبل وجود دارد')}",
            status_code=303
        )


@router.post("/warehouse")
async def create_warehouse(
    name: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """تعریف انبار فیزیکی جدید"""
    try:
        db.add(Warehouse(name=name.strip()))
        db.commit()
        return RedirectResponse(url="/dashboard?msg=" + quote("انبار جدید با موفقیت ثبت شد"), status_code=303)
    except IntegrityError:
        db.rollback()
        return RedirectResponse(url="/dashboard?error=" + quote("این انبار از قبل در سیستم وجود دارد"), status_code=303)