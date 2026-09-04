from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# استفاده از دیتابیس لوکال برای توسعه و تست سریع (Zero-Config)
SQLALCHEMY_DATABASE_URL = "sqlite:///./enterprise_erp.db"

# پارامتر check_same_thread مخصوص SQLite در محیط‌های چندنخی (FastAPI) است
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# کارخانه تولید نشست‌های دیتابیس (ACID Compliant)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# کلاس پایه برای ارث‌بری تمام مدل‌های دیتابیس
Base = declarative_base()

# سیستم تزریق وابستگی (Dependency Injection) برای کنترلرها
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()