import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

# آدرس دیتابیس از فایل .env خوانده می‌شود
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://erp_user:super_secure_password_123@localhost:5432/storage_erp"
)

# تضمین استفاده از درایور psycopg2
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

# کارخانه تولید نشست‌های دیتابیس
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# کلاس پایه یکتا برای ارث‌بری تمام مدل‌های دیتابیس
Base = declarative_base()

def get_db():
    """تزریق وابستگی برای مدیریت امن نشست‌های پایگاه‌داده"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()