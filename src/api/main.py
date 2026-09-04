from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# فراخوانی کنترلرهای سیستم
from src.api import auth
from src.api import ui
from src.api import inventory_ui
from src.api import master_data_ui

# فراخوانی زیرساخت دیتابیس و مدل‌ها
from src.infrastructure.database import engine, SessionLocal, Base
from src.domain_model import inventory_models
from src.domain_model import user_models
from src.api.auth import get_password_hash

# ساخت تمام جداول (انبار و کاربران) در دیتابیس
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    چرخه حیات سرور: بررسی و تزریق داده‌های پایه (Master Data & Admin Seeding)
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
            
        # ۳. ساخت نقش‌های سیستمی (Roles)
        if not db.query(user_models.Role).first():
            admin_role = user_models.Role(name="Admin", description="مدیر کل سیستم")
            operator_role = user_models.Role(name="Warehouse_Operator", description="اپراتور انبار")
            db.add_all([admin_role, operator_role])
            db.commit() # کامیت برای دریافت ID نقش‌ها
            
        # ۴. ساخت کاربر مدیر کل (Admin)
        if not db.query(user_models.User).filter_by(username="admin").first():
            admin_role = db.query(user_models.Role).filter_by(name="Admin").first()
            
            # هش کردن رمز عبور پیش‌فرض برای امنیت پایگاه‌داده
            hashed_pw = get_password_hash("admin123")
            
            admin_user = user_models.User(
                username="admin",
                hashed_password=hashed_pw,
                full_name="مدیر کل سیستم",
                is_active=True
            )
            # انتساب نقش مدیر به کاربر
            admin_user.roles.append(admin_role)
            db.add(admin_user)

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

# اتصال پوشه استاتیک
app.mount("/static", StaticFiles(directory="static"), name="static")

# رجیستر کردن روت‌های ماژول‌ها
app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)
app.include_router(master_data_ui.router)

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Enterprise ERP API is running. Go to /login"}