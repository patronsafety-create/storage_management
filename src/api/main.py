from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api import auth
from src.api import ui
from src.api import inventory_ui

from src.infrastructure.database import engine, SessionLocal
from src.domain_model import inventory_models

# ساخت فیزیکی جداول در دیتابیس
inventory_models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    این تابع در زمان استارت سرور اجرا می‌شود.
    وظیفه آن بررسی دیتابیس و تزریق داده‌های اولیه (Data Seeding) است.
    """
    db = SessionLocal()
    try:
        # ساخت انبارهای پیش‌فرض در صورت خالی بودن جدول
        if not db.query(inventory_models.Warehouse).first():
            db.add_all([
                inventory_models.Warehouse(name="انبار شماره یک"),
                inventory_models.Warehouse(name="انبار شماره دو")
            ])
            
        # ساخت کالاهای پیش‌فرض با واحد سنجش (تناژ)
        if not db.query(inventory_models.Product).first():
            db.add_all([
                inventory_models.Product(name="شمش آهن", uom="تن"),
                inventory_models.Product(name="اوره گرانول", uom="تن")
            ])
        db.commit()
    finally:
        db.close()
    yield

app = FastAPI(
    title="Storage ERP API",
    description="سیستم مدیریت انبار و احراز هویت",
    version="1.0.0",
    lifespan=lifespan  # اتصال چرخه حیات به هسته برنامه
)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Enterprise ERP API is running"}