from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# راه‌اندازی نمونه اصلی اپلیکیشن با مستندات خودکار
app = FastAPI(
    title="Storage Management ERP",
    description="سیستم جامع انبارداری، حسابداری و حقوق و دستمزد",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# تنظیمات CORS برای دسترسی رابط کاربری (Frontend) تحت وب از روی شبکه داخلی (LAN) یا سرور ابری
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
def health_check():
    """
    سرویس بررسی سلامت سیستم برای مانیتورینگ وضعیت سرور
    """
    return {
        "status": "online",
        "message": "ERP Core Service is running successfully."
    }