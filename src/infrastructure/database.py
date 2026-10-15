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

try:
    if "postgresql" in DATABASE_URL:
        # تست سریع در دسترس بودن سرور پستگرس (timeout = 2 ثانیه)
        _test_engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"connect_timeout": 2}
        )
        with _test_engine.connect() as _conn:
            pass
        engine = _test_engine
    else:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800)
except Exception as _db_err:
    # فال‌بک خودکار به SQLite جهت اطمینان از بالا آمدن بی‌نقص سرور در محیط توسعه لوکال ویندوز بدون داکر
    print(f"\n[NexusPour ERP] PostgreSQL is not reachable locally: {_db_err}")
    print("[NexusPour ERP] Active Engine: Local SQLite (storage_erp.db) enabled for seamless local execution.\n")
    DATABASE_URL = "sqlite:///storage_erp.db"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=1800, connect_args={"check_same_thread": False})

# کارخانه تولید نشست‌های دیتابیس
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# کلاس پایه یکتا برای ارث‌بری تمام مدل‌های دیتابیس
Base = declarative_base()

def get_db():
    """تزریق وابستگی برای مدیریت امن نشست‌های پایگاه‌داده با محافظت کامل در برابر قفل‌شدگی"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()