"""
مدیریت و تزریق کاربران و ۵ نقش استاندارد سازمانی سامانه NexusPour ERP
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
        "role_desc": "مدیر ارشد سیستم - دسترسی کامل به همه بخش‌ها"
    },
    {
        "username": "finance",
        "full_name": "مدیر مالی و حسابداری",
        "role_name": "Finance_Manager",
        "role_desc": "مدیر مالی و حسابداری (کاردکس ریالی، اصلاحیه، سال مالی، مرجوعی، گزارشات خرید/فروش)"
    },
    {
        "username": "warehouse",
        "full_name": "سرپرست انبار",
        "role_name": "Warehouse_Supervisor",
        "role_desc": "سرپرست انبار (کارتابل تایید/رد اسناد انبار، ثبت رسید/حواله، انتقال، انبارگردانی، مرجوعی، کیسه‌گیری اوره)"
    },
    {
        "username": "commercial",
        "full_name": "کارشناس بازرگانی (خرید و فروش)",
        "role_name": "Commercial_Officer",
        "role_desc": "کارشناس بازرگانی (خرید و فروش) (تعریف و ویرایش تامین‌کننده و مشتری، ثبت و مدیریت سفارشات خرید PO و سفارشات فروش SO)"
    },
    {
        "username": "baskool",
        "full_name": "اپراتور باسکول دیجیتال",
        "role_name": "Weighbridge_Operator",
        "role_desc": "اپراتور باسکول دیجیتال (ثبت نوبت و توزین اول و دوم باسکول)"
    }
]

def seed_enterprise_users(db: Session):
    """
    ایجاد خودکار یا به‌روزرسانی ۵ نقش و کاربر کلیدی سامانه با رمز عبور ۱۲۳۴
    جهت تست سریع، تفکیک وظایف (SoD) و انطباق با استاندارد ERP.
    """
    hashed_pwd = get_password_hash("1234")

    # ۱. ایجاد یا به‌روزرسانی نقش‌های ۵ گانه
    for item in TEST_USERS_DATA:
        role = db.query(Role).filter_by(name=item["role_name"]).first()
        if not role:
            role = Role(name=item["role_name"], description=item["role_desc"])
            db.add(role)
            db.flush()
        else:
            role.description = item["role_desc"]

    db.flush()

    # ۲. ایجاد یا به‌روزرسانی ۵ کاربر با رمز 1234
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
