from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from src.api import auth, ui, inventory_ui, master_data_ui, admin_ui, stock_api
from src.infrastructure.database import engine, SessionLocal, Base
from src.domain_model import inventory_models, auth_models
from src.infrastructure.security import get_password_hash

# ساخت تمام جداول دیتابیس
Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """تزریق داده‌های پایه (Seeding) هنگام راه‌اندازی برنامه"""
    db = SessionLocal()
    try:
        # ۱. انبارهای پیش‌فرض
        if not db.query(inventory_models.Warehouse).first():
            db.add_all([
                inventory_models.Warehouse(name="انبار شماره یک"),
                inventory_models.Warehouse(name="انبار شماره دو")
            ])

        # ۲. کالاهای پیش‌فرض
        if not db.query(inventory_models.Product).first():
            db.add_all([
                inventory_models.Product(name="شمش آهن", uom="تن"),
                inventory_models.Product(name="اوره گرانول", uom="تن")
            ])

        # ۳. نقش‌های سیستمی
        if not db.query(auth_models.Role).first():
            db.add_all([
                auth_models.Role(name="Admin", description="مدیر کل سیستم"),
                auth_models.Role(name="Warehouse_Operator", description="اپراتور انبار")
            ])
            db.commit()

        # ۴. کاربر Admin
        admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
        if not db.query(auth_models.User).filter_by(username="admin").first():
            admin_role = db.query(auth_models.Role).filter_by(name="Admin").first()
            admin_user = auth_models.User(
                username="admin",
                hashed_password=get_password_hash(admin_password),
                full_name="مدیر کل سیستم",
                is_active=True
            )
            admin_user.roles.append(admin_role)
            db.add(admin_user)

        # ۵. کاربر Operator
        operator_password = os.getenv("OPERATOR_PASSWORD", "operator123")
        if not db.query(auth_models.User).filter_by(username="operator").first():
            operator_role = db.query(auth_models.Role).filter_by(name="Warehouse_Operator").first()
            operator_user = auth_models.User(
                username="operator",
                hashed_password=get_password_hash(operator_password),
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
    title="NexusPour ERP API",
    description="سامانه یکپارچه انبارداری نکسوس‌پور (NexusPour ERP) — طراحی و مهندسی: امید پورمحمود",
    version="2.0.0",
    lifespan=lifespan
)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code
    )


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)
app.include_router(master_data_ui.router)
app.include_router(admin_ui.router)
app.include_router(stock_api.router)


@app.get("/", tags=["General"])
def read_root():
    return RedirectResponse(url="/dashboard")