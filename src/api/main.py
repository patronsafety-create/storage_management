from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.api import auth
from src.api import ui
from src.api import inventory_ui  # اضافه شدن ماژول انبار

app = FastAPI(
    title="Storage ERP API",
    description="سیستم مدیریت انبار و احراز هویت",
    version="1.0.0"
)

# اتصال پوشه استاتیک برای فایل‌های CSS و فونت‌ها
app.mount("/static", StaticFiles(directory="static"), name="static")

# رجیستر کردن روترهای سیستم
app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)  # اتصال روتر انبار به هسته مرکزی

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Enterprise ERP API is running"}