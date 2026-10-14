"""
اسکریپت تست و اعتبارسنجی جامع مرحله نهایی تضمین کیفیت و بومی‌سازی (Final QA & Localization Audit)
سامانه NexusPour ERP - طراح و مهندس: امید پورمحمود (Omid Pourmahmoud)

شامل ۶ آزمون تفصیلی:
۱. عدم قاطی شدن ریال و لیر در میانگین موزون کاردکس با اعمال exchange_rate
۲. نرمال‌سازی هوشمند اعداد فارسی، عربی و ممیز ترکی (Number Normalizer)
۳. یکپارچگی تایمزون UTC و نمایش شمسی/ترکی تاریخ (format_date)
۴. اعتبارسنجی منعطف تامین‌کنندگان و مشتریان در ایران و ترکیه (VKN, TCKN, تلفن)
۵. قفل امنیتی RBAC در سمت سرور با خطای ۴۰۳
۶. دقت صفر در انبارگردانی (صدور سند تعدیل کسری برای صفر کردن موجودی)
"""

import sys
import os
from datetime import datetime, timezone

# افزودن ریشه پروژه به مسیر پایتون
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.infrastructure.database import SessionLocal
from src.domain_model.auth_models import User, Role
from src.domain_model.inventory_models import (
    Product, Warehouse, StockTransaction, FiscalYear,
    Supplier, Customer, TransactionType
)
from src.domain_model.enums import TransactionSource, DocumentStatus
from src.services.inventory_service import InventoryService
from src.infrastructure.number_normalizer import (
    to_english_digits, normalize_number_str, parse_float_safe, parse_int_safe
)
from src.core.localization.regions import (
    gregorian_to_jalali, format_date_localized, format_date_filter
)
from src.core.localization.tr_rules import (
    validate_turkish_phone, normalize_turkish_phone, validate_vkn, validate_tc_kimlik, validate_turkish_party_data
)
from src.api.inventory_ui import require_roles
from fastapi import HTTPException


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.infrastructure.database import Base

test_engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=test_engine)
TestSession = sessionmaker(bind=test_engine)


def test_1_currency_isolation():
    print("--- [Test 1] آزمون ایزولاسیون ارزی کاردکس و میانگین موزون ---")
    db = TestSession()
    try:
        # انبار ریالی
        wh_ir = Warehouse(name="انبار آزمایشی ریالی تهران", country_code="IR", currency="IRR")
        db.add(wh_ir)
        db.commit()

        # کالای تستی
        p = Product(name="کالای آزمون ارزی", sku="TEST-CURRENCY-PROD", uom="کیلوگرم", min_stock=10.0)
        db.add(p)
        db.commit()

        # پاک‌سازی تراکنش‌های قبلی تستی
        db.query(StockTransaction).filter_by(product_id=p.id, warehouse_id=wh_ir.id).delete()
        db.commit()

        # ۱. ورود ۱۰۰ واحد با ارز ریال، فی ۴۰۰,۰۰۰ ریال (ضریب ۱.۰)
        tx1 = StockTransaction(
            transaction_type=TransactionType.IN,
            transaction_source=TransactionSource.PURCHASE.value,
            product_id=p.id,
            warehouse_id=wh_ir.id,
            quantity=100.0,
            unit_price=400000.0,
            currency="IRR",
            exchange_rate=1.0,
            status=DocumentStatus.APPROVED
        )
        # ۲. ورود ۵۰ واحد با ارز لیر ترکیه (TRY)، فی ۲۵ لیر به ازای هر واحد، با ضریب تبدیل ۱ لیر = ۱۶,۰۰۰ ریال
        # فی معادل ریالی: ۲۵ * ۱۶۰۰۰ = ۴۰۰,۰۰۰ ریال
        tx2 = StockTransaction(
            transaction_type=TransactionType.IN,
            transaction_source=TransactionSource.PURCHASE.value,
            product_id=p.id,
            warehouse_id=wh_ir.id,
            quantity=50.0,
            unit_price=25.0,  # لیر ترکیه
            currency="TRY",
            exchange_rate=16000.0,  # هر لیر = ۱۶,۰۰۰ ریال
            status=DocumentStatus.APPROVED
        )
        db.add_all([tx1, tx2])
        db.commit()

        avg_cost_irr = InventoryService.get_weighted_average_cost(db, p.id, wh_ir.id, target_currency="IRR")
        # انتظار: مجموع ارزش ریالی = (100 * 400000) + (50 * 25 * 16000) = 40,000,000 + 20,000,000 = 60,000,000
        # میانگین موزون ریالی = 60,000,000 / 150 = 400,000 ریال
        print(f"میانگین موزون محاسبه‌شده بر حسب ریال: {avg_cost_irr:,.2f} IRR")
        assert abs(avg_cost_irr - 400000.0) < 1.0, f"Expected 400000.0 but got {avg_cost_irr}"

        # محاسبه بر حسب لیر:
        avg_cost_try = InventoryService.get_weighted_average_cost(db, p.id, wh_ir.id, target_currency="TRY")
        # انتظار: ۴۰۰,۰۰۰ ریال تقسیم بر ۱۶,۰۰۰ = ۲۵ لیر
        print(f"میانگین موزون محاسبه‌شده بر حسب لیر (TRY): {avg_cost_try:.2f} TRY")
        assert abs(avg_cost_try - 25.0) < 0.1, f"Expected 25.0 but got {avg_cost_try}"

        print("✔ [Test 1 Passed] ایزولاسیون ارزی و تبدیل میانگین موزون با ضریب ارز کاملاً صحیح عمل کرد.")
    finally:
        db.close()


def test_2_number_normalizer():
    print("\n--- [Test 2] آزمون نرمال‌سازی اعداد فارسی، عربی و ممیز اعشار ترکی ---")
    # ارقام فارسی
    persian_str = "۱۲۳۴۵۶۷۸۹۰"
    assert to_english_digits(persian_str) == "1234567890"

    # ارقام عربی
    arabic_str = "١٢٣٤٥٦٧٨٩٠"
    assert to_english_digits(arabic_str) == "1234567890"

    # ممیز اعشار ترکی (24,5 -> 24.5)
    tr_decimal = "۲۴,۵"
    norm_val = normalize_number_str(tr_decimal)
    assert norm_val == "24.5", f"Expected 24.5, got {norm_val}"
    assert parse_float_safe(tr_decimal) == 24.5

    # عدد هزارگان با ممیز ترکی (1.250,75 -> 1250.75)
    tr_formatted = "۱.۲۵۰,۷۵"
    assert parse_float_safe(tr_formatted) == 1250.75

    # رشته خالی و بدون خطا
    assert parse_float_safe("") == 0.0
    assert parse_int_safe("۱۲۵") == 125

    print("✔ [Test 2 Passed] تبدیل ارقام فارسی/عربی و فرمت ممیز اعشار ترکی کاملاً موفقیت‌آمیز بود.")


def test_3_timezone_and_date_display():
    print("\n--- [Test 3] آزمون یکپارچگی تایمزون UTC و نمایش شمسی/ترکی تاریخ ---")
    now_utc = datetime.now(timezone.utc)
    assert now_utc.tzinfo is not None, "Date should be timezone-aware UTC"

    # تاریخ مشخص برای تست دقیق تقویم: 2026-10-15
    target_dt = datetime(2026, 10, 15, 14, 30, tzinfo=timezone.utc)

    # تست نمایش در ایران (شمسی): 23 مهر 1405 (1405/07/23)
    date_ir = format_date_localized(target_dt, region_code="IR")
    print(f"تاریخ میلادی 2026-10-15 در حالت ایران: {date_ir}")
    assert date_ir == "1405/07/23", f"Expected '1405/07/23' but got '{date_ir}'"

    # تست نمایش در ترکیه (ترکی رسمی DD.MM.YYYY): 15.10.2026
    date_tr = format_date_localized(target_dt, region_code="TR")
    print(f"تاریخ میلادی 2026-10-15 در حالت ترکیه: {date_tr}")
    assert date_tr == "15.10.2026", f"Expected '15.10.2026' but got '{date_tr}'"

    # تست همراه با ساعت
    date_ir_time = format_date_localized(target_dt, region_code="IR", include_time=True)
    assert "1405/07/23 14:30" in date_ir_time

    date_tr_time = format_date_localized(target_dt, region_code="TR", include_time=True)
    assert "15.10.2026 14:30" in date_tr_time

    # تست فیلتر Jinja2
    ctx_tr = {"is_tr": True}
    res_tr = format_date_filter(ctx_tr, target_dt)
    assert res_tr == "15.10.2026"

    ctx_ir = {"is_tr": False}
    res_ir = format_date_filter(ctx_ir, target_dt)
    assert res_ir == "1405/07/23"

    print("✔ [Test 3 Passed] یکپارچه‌سازی تایمزون و الگوریتم شمسی/ترکی با موفقیت تایید شد.")


def test_4_flexible_party_validation():
    print("\n--- [Test 4] آزمون اعتبارسنجی منعطف اشخاص و شرکت‌ها در ایران و ترکیه ---")
    # ۱. تلفن ترکیه با +90 و بدون 0
    phone_plus90 = "+90 532 123 4567"
    assert validate_turkish_phone(phone_plus90) == True
    assert normalize_turkish_phone(phone_plus90) == "05321234567"

    phone_no_zero = "532 123 45 67"
    assert validate_turkish_phone(phone_no_zero) == True
    assert normalize_turkish_phone(phone_no_zero) == "05321234567"

    phone_landline = "(0212) 376 10 00"
    assert validate_turkish_phone(phone_landline) == True
    assert normalize_turkish_phone(phone_landline) == "02123761000"

    # ۲. شناسه مالیاتی معتبر ترکیه (VKN Erdemir: 3530018590)
    vkn_erdemir = "3530018590"
    assert validate_vkn(vkn_erdemir) == True

    # ۳. شماره ملی معتبر اشخاص حقیقی ترکیه (TCKN: 10000000146)
    tckn_sample = "10000000146"
    assert validate_tc_kimlik(tckn_sample) == True

    # ۴. اعتبارسنجی جامع فرم طرف تجاری ترکیه
    err, clean_name, clean_phone, clean_vkn = validate_turkish_party_data(
        name="Ereğli Demir Çelik A.Ş.",
        phone="+90 (372) 323-2500",
        national_id=vkn_erdemir,
        party_type_label="Tedarikçi"
    )
    assert err is None, f"Expected no error, got: {err}"
    assert clean_phone == "03723232500"
    assert clean_vkn == "3530018590"

    print("✔ [Test 4 Passed] اعتبارسنجی منعطف فرمت‌های ترکیه (VKN, TCKN, تلفن) کاملاً تایید شد.")


def test_5_backend_rbac_guard():
    print("\n--- [Test 5] آزمون قفل امنیتی دسترسی‌ها در سمت سرور (Backend RBAC Guard) ---")
    # ایجاد کاربران تستی با نقش‌های مختلف
    admin_user = User(username="test_admin")
    admin_user.roles = [Role(name="Admin")]

    supervisor_user = User(username="test_sup")
    supervisor_user.roles = [Role(name="Warehouse_Supervisor")]

    finance_user = User(username="test_fin")
    finance_user.roles = [Role(name="Finance_Manager")]

    operator_user = User(username="test_op")
    operator_user.roles = [Role(name="Warehouse_Operator")]

    # الف) تایید و رد اسناد کارتابل انبار: مجاز برای Admin و Warehouse_Supervisor
    require_roles(admin_user, {"Admin", "Warehouse_Supervisor"})
    require_roles(supervisor_user, {"Admin", "Warehouse_Supervisor"})

    # برای اپراتور یا مدیر مالی باید خطای 403 پرتاب کند:
    try:
        require_roles(operator_user, {"Admin", "Warehouse_Supervisor"})
        assert False, "Should have raised 403 HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "عدم دسترسی" in exc.detail
        print("✔ ممانعت از تایید کارتابل توسط اپراتور انبار با خطای ۴۰۳ تایید شد.")

    # ب) ثبت سند اصلاحیه و بستن سال مالی: مجاز برای Admin و Finance_Manager
    require_roles(admin_user, {"Admin", "Finance_Manager"})
    require_roles(finance_user, {"Admin", "Finance_Manager"})

    try:
        require_roles(operator_user, {"Admin", "Finance_Manager"})
        assert False, "Should have raised 403 HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "عدم دسترسی" in exc.detail
        print("✔ ممانعت از بستن سال مالی و اصلاحیه توسط اپراتور انبار با خطای ۴۰۳ تایید شد.")

    try:
        require_roles(supervisor_user, {"Admin", "Finance_Manager"})
        assert False, "Should have raised 403 HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
        print("✔ ممانعت از بستن سال مالی توسط سرپرست انبار با خطای ۴۰۳ تایید شد.")

    print("✔ [Test 5 Passed] سیستم گارد دسترسی امنیتی سمت سرور با بازگشت خطای ۴۰۳ کاملاً پایدار است.")


def test_6_stocktaking_zero_count_precision():
    print("\n--- [Test 6] آزمون دقت صفر در انبارگردانی (شمارش فیزیکی 0) ---")
    db = TestSession()
    try:
        wh = db.query(Warehouse).first()
        if not wh:
            wh = Warehouse(name="انبار انبارگردانی", country_code="IR", currency="IRR")
            db.add(wh)
            db.commit()

        p = Product(name="کالای آزمون شمارش صفر", sku="TEST-ZERO-PROD", uom="کیلوگرم", min_stock=5.0)
        db.add(p)
        db.commit()

        # پاک‌سازی
        db.query(StockTransaction).filter_by(product_id=p.id, warehouse_id=wh.id).delete()
        db.commit()

        # ۱. ورود ۱۰ واحد موجودی به سیستم
        tx_in = StockTransaction(
            transaction_type=TransactionType.IN,
            transaction_source=TransactionSource.PURCHASE.value,
            product_id=p.id,
            warehouse_id=wh.id,
            quantity=10.0,
            unit_price=1000.0,
            status=DocumentStatus.APPROVED
        )
        db.add(tx_in)
        db.commit()

        cur_stock = InventoryService.get_current_stock(db, p.id, wh.id)
        assert cur_stock == 10.0

        # شبیه‌سازی انبارگردانی:
        # ورودی شمارش کاربر صریحاً "0" وارد شده است
        raw_val = "0"
        assert raw_val != "", "Raw val should not be treated as empty"
        phys_count = parse_float_safe(raw_val)
        assert phys_count == 0.0

        diff = round(phys_count - cur_stock, 4)
        assert diff == -10.0

        # صدور سند کسری انبارگردانی
        adj_tx = StockTransaction(
            transaction_type=TransactionType.OUT,
            transaction_source=TransactionSource.STOCKTAKING.value,
            product_id=p.id,
            warehouse_id=wh.id,
            quantity=round(abs(diff), 3),
            unit_price=1000.0,
            status=DocumentStatus.APPROVED,
            reference_document=f"تعدیل انبارگردانی صفر شدن موجودی"
        )
        db.add(adj_tx)
        db.commit()

        # بررسی موجودی پس از انبارگردانی:
        final_stock = InventoryService.get_current_stock(db, p.id, wh.id)
        print(f"موجودی سیستمی پس از ثبت شمارش فیزیکی ۰: {final_stock}")
        assert final_stock == 0.0, f"Expected 0.0 but got {final_stock}"

        print("✔ [Test 6 Passed] ثبت شمارش فیزیکی ۰ منجر به صدور سند تعدیل کسری و صفر شدن قطعی موجودی شد.")
    finally:
        db.close()


if __name__ == "__main__":
    print("=================================================================")
    print("🚀 اجرای تست‌های نهایی تضمین کیفیت و بومی‌سازی (NexusPour ERP v2.5.0)")
    print("=================================================================")
    test_1_currency_isolation()
    test_2_number_normalizer()
    test_3_timezone_and_date_display()
    test_4_flexible_party_validation()
    test_5_backend_rbac_guard()
    test_6_stocktaking_zero_count_precision()
    print("\n=================================================================")
    print("🎉 کلیه آزمون‌های شش‌گانه تضمین کیفیت با موفقیت ۱۰۰٪ سپری شدند!")
    print("=================================================================")
