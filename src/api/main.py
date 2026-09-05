from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import RedirectResponse, HTMLResponse

# فراخوانی کنترلرهای سیستم
from src.api import auth
from src.api import ui
from src.api import inventory_ui
from src.api import master_data_ui

from src.infrastructure.database import engine, SessionLocal, Base
from src.domain_model import inventory_models
from src.domain_model import user_models
from src.api.auth import get_password_hash

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        if not db.query(inventory_models.Warehouse).first():
            db.add_all([
                inventory_models.Warehouse(name="انبار شماره یک"),
                inventory_models.Warehouse(name="انبار شماره دو")
            ])
            
        if not db.query(inventory_models.Product).first():
            db.add_all([
                inventory_models.Product(name="شمش آهن", uom="تن"),
                inventory_models.Product(name="اوره گرانول", uom="تن")
            ])
            
        if not db.query(user_models.Role).first():
            admin_role = user_models.Role(name="Admin", description="مدیر کل سیستم")
            operator_role = user_models.Role(name="Warehouse_Operator", description="اپراتور انبار")
            db.add_all([admin_role, operator_role])
            db.commit()
            
        if not db.query(user_models.User).filter_by(username="admin").first():
            admin_role = db.query(user_models.Role).filter_by(name="Admin").first()
            hashed_pw = get_password_hash("admin123")
            admin_user = user_models.User(
                username="admin",
                hashed_password=hashed_pw,
                full_name="مدیر کل سیستم",
                is_active=True
            )
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

# === سیستم هدایت هوشمند کاربران بدون دسترسی ===
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        # اگر کاربر احراز هویت نشده بود، به جای ارور خام، به صفحه ورود هدایت می‌شود
        return RedirectResponse(url="/login")
    return HTMLResponse(content=f"<h3>خطای سیستمی: {exc.detail}</h3>", status_code=exc.status_code)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)
app.include_router(master_data_ui.router)

@app.get("/", tags=["General"])
def read_root():
    # انتقال مستقیم از ریشه سایت به داشبورد (که خود داشبورد کاربر را چک می‌کند)
    return RedirectResponse(url="/dashboard")