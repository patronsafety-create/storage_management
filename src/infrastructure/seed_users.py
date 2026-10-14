"""
مدیریت و تزریق کاربران و نقش‌های آزمایشی و پیش‌فرض سامانه NexusPour ERP
رمز عبور پیش‌فرض تمام کاربران آزمایشی: 1234
طراحی و مهندسی: امید پورمحمود (Omid Pourmahmoud)
"""
from sqlalchemy.orm import Session
from src.domain_model.auth_models import Role, User
from src.infrastructure.security import get_password_hash

TEST_USERS_DATA = [
    {
        "username": "admin",
        "full_name": "مدیر ارشد سیستم (امید پورمحمود)",
        "role_name": "Admin",
        "role_desc": "مدیر کل و معمار ارشد سیستم - دسترسی کامل به تمامی بخش‌ها"
    },
    {
        "username": "finance",
        "full_name": "مدیر مالی و حسابرسی",
        "role_name": "Finance_Manager",
        "role_desc": "مدیریت حسابداری، کاردکس ریالی، اصلاحیه‌ها، بستن سال مالی، گزارشات مالی خرید و فروش"
    },
    {
        "username": "warehouse",
        "full_name": "سرپرست انبار مرکزی",
        "role_name": "Warehouse_Supervisor",
        "role_desc": "کارتابل تأیید اسناد انبار، موجودی لحظه‌ای، حواله انتقال، انبارگردانی، مرجوعی کالا"
    },
    {
        "username": "buyer",
        "full_name": "کارشناس بازرگانی خرید",
        "role_name": "Procurement_Officer",
        "role_desc": "مدیریت تأمین‌کنندگان، ثبت سفارشات خرید (PO) و پیگیری ورود بار"
    },
    {
        "username": "seller",
        "full_name": "کارشناس بازرگانی فروش",
        "role_name": "Sales_Officer",
        "role_desc": "مدیریت مشتریان، صدور پیش‌فاکتور و سفارشات فروش (SO) و حواله تحویل"
    },
    {
        "username": "baskool",
        "full_name": "اپراتور باسکول دیجیتال",
        "role_name": "Weighbridge_Operator",
        "role_desc": "عملیات توزین اول و دوم ناوگان سنگین و ثبت قبوض باسکول"
    },
    {
        "username": "workshop",
        "full_name": "مسئول کارگاه برش و کیسه‌گیری",
        "role_name": "Production_Operator",
        "role_desc": "دستورات برش آهن و پروفیل، مدیریت ته‌شاخه و کیسه‌گیری فله اوره"
    }
]

def seed_enterprise_users(db: Session):
    """
    ایجاد خودکار یا به‌روزرسانی ۷ نقش و کاربر کلیدی سامانه با رمز عبور ۱۲۳۴
    جهت تست سریع، تفکیک وظایف (SoD) و بررسی سناریوهای واقعی ERP.
    """
    hashed_pwd = get_password_hash("1234")

    # ۱. ایجاد یا به‌روزرسانی نقش‌ها
    for item in TEST_USERS_DATA:
        role = db.query(Role).filter_by(name=item["role_name"]).first()
        if not role:
            role = Role(name=item["role_name"], description=item["role_desc"])
            db.add(role)
            db.flush()
        else:
            role.description = item["role_desc"]

    # همچنین نقش پیش‌فرض Warehouse_Operator اگر قبلاً بوده
    if not db.query(Role).filter_by(name="Warehouse_Operator").first():
        db.add(Role(name="Warehouse_Operator", description="اپراتور انبار"))
    db.flush()

    # ۲. ایجاد یا به‌روزرسانی کاربران با رمز 1234
    for item in TEST_USERS_DATA:
        role = db.query(Role).filter_by(name=item["role_name"]).first()
        user = db.query(User).filter_by(username=item["username"]).first()
        if not user:
            user = User(
                username=item["username"],
                hashed_password=hashed_pwd,
                full_name=item["full_name"],
                is_active=True
            )
            if role:
                user.roles.append(role)
            db.add(user)
        else:
            # همواره برای تست سریع، رمز به 1234 تنظیم و فعال باشد
            user.hashed_password = hashed_pwd
            user.full_name = item["full_name"]
            user.is_active = True
            if role and role not in user.roles:
                user.roles.append(role)

    # به‌روزرسانی کاربر قدیمی operator به 1234 در صورت وجود
    op_user = db.query(User).filter_by(username="operator").first()
    if op_user:
        op_user.hashed_password = hashed_pwd
        op_user.is_active = True

    db.commit()
