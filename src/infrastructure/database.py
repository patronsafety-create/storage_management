import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# مسیر دیتابیس به صورت متغیر محیطی (Env Var) تعریف می‌شود تا انتقال از لپ‌تاپ به سرور اوراکل بدون تغییر کد انجام شود.
# فرمت: postgresql://username:password@host:port/database_name
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:123456@localhost:5432/storage_erp")

# تنظیمات Engine با استفاده از Connection Pooling برای جلوگیری از فشار مضاعف به سرور دیتابیس
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # بررسی سلامت کانکشن‌ها قبل از ارسال کوئری
    pool_size=10,        # حداکثر کانکشن‌های همزمان پایه
    max_overflow=20      # کانکشن‌های رزرو در زمان اوج مصرف
)

# ایجاد سازنده نشست (SessionMaker) برای تراکنش‌های دیتابیس
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency برای مدیریت چرخه حیات کانکشن‌ها در APIها
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()