from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

# فراخوانی روترهای سیستم
from src.api import auth
from src.api import ui
from src.api import inventory_ui
from src.api import master_data_ui

# فراخوانی لایه‌های زیرساخت و دامنه
from src.infrastructure.database import engine, SessionLocal, Base
from src.domain_model import inventory_models
from src.domain_model import user_models
from src.api.auth import get_password_hash

# ساخت جداول دیتابیس
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    تزریق داده‌های پایه (Master Data) و حساب‌های کاربری (Seeding)
    """
    db = SessionLocal()
    try:
        # ۱. ساخت انبارهای پیش‌فرض
        if not db.query(inventory_models.Warehouse).first():
            db.add_all([
                inventory_models.Warehouse(name="انبار شماره یک"),
                inventory_models.Warehouse(name="انبار شماره دو")
            ])
            
        # ۲. ساخت کالاهای پیش‌فرض
        if not db.query(inventory_models.Product).first():
            db.add_all([
                inventory_models.Product(name="شمش آهن", uom="تن"),
                inventory_models.Product(name="اوره گرانول", uom="تن")
            ])
            
        # ۳. ساخت نقش‌های سیستمی (RBAC Roles)
        if not db.query(user_models.Role).first():
            admin_role = user_models.Role(name="Admin", description="مدیر کل سیستم")
            operator_role = user_models.Role(name="Warehouse_Operator", description="اپراتور انبار")
            db.add_all([admin_role, operator_role])
            db.commit()
            
        # ۴. ساخت کاربر مدیر کل (Admin)
        if not db.query(user_models.User).filter_by(username="admin").first():
            admin_role = db.query(user_models.Role).filter_by(name="Admin").first()
            admin_user = user_models.User(
                username="admin",
                hashed_password=get_password_hash("admin123"),
                full_name="مدیر کل سیستم",
                is_active=True
            )
            admin_user.roles.append(admin_role)
            db.add(admin_user)

        # ۵. 🌟 ساخت کاربر اپراتور انبار (Warehouse Operator)
        if not db.query(user_models.User).filter_by(username="operator").first():
            operator_role = db.query(user_models.Role).filter_by(name="Warehouse_Operator").first()
            operator_user = user_models.User(
                username="operator",
                hashed_password=get_password_hash("operator123"),
                full_name="کارمند انبار (اپراتور)",
                is_active=True
            )
            operator_user.roles.append(operator_role)
            db.add(operator_user)

        db.commit()
    finally:
        db.close()
    yield

app = FastAPI(
    title="Storage ERP API",
    description="سیستم مدیریت انبار و احراز هویت",
    version="1.0.0",
    lifespan=lifespan
)

# === سیستم هدایت هوشمند کاربران بدون دسترسی ===
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return HTMLResponse(content=f"<h3>خطای سیستمی: {exc.detail}</h3>", status_code=exc.status_code)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)
app.include_router(master_data_ui.router)

@app.get("/", tags=["General"])
def read_root():
    return RedirectResponse(url="/dashboard")