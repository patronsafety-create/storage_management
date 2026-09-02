from fastapi import FastAPI
from src.api import auth
from src.api import ui

# مقداردهی اولیه اپلیکیشن FastAPI
app = FastAPI(
    title="Storage ERP API",
    description="سیستم مدیریت انبار و احراز هویت",
    version="1.0.0"
)

# اتصال ماژول احراز هویت (Login) به اپلیکیشن اصلی
app.include_router(auth.router)
app.include_router(ui.router)
# روت اصلی برای تست سلامت سرور

@app.get("/", tags=["General"])
def read_root():
    return {"message": "Storage ERP API is running"}