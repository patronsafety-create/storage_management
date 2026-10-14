"""
NexusPour ERP - Test Suite for Part 4 (Turkey Localization: KDV 20% & Demir-Çelik Tevkifatı 4/10)
Owner & Architect: Omid Pourmahmoud
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.database import Base
from src.domain_model.inventory_models import PurchaseOrder, PurchaseOrderItem, Supplier, Product, ProductCategory
from src.domain_model.enums import PurchaseOrderStatus
from src.services.tax_service import TaxService, TaxCalculationResult

def make_request(cookie_region=None):
    headers = []
    if cookie_region:
        headers.append((b"cookie", f"nexus_region={cookie_region}".encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/purchases/1",
        "headers": headers,
    }
    return Request(scope)

def run_tests():
    print("==================================================")
    print("Running Part 4 Tests: Turkish KDV & Steel Tevkifat Engine")
    print("==================================================")

    # ۱. تست مدل PurchaseOrder: وجود ستون‌های مالی و مالیاتی
    assert hasattr(PurchaseOrder, "subtotal_amount"), "PurchaseOrder must have subtotal_amount"
    assert hasattr(PurchaseOrder, "vat_rate"), "PurchaseOrder must have vat_rate"
    assert hasattr(PurchaseOrder, "vat_amount"), "PurchaseOrder must have vat_amount"
    assert hasattr(PurchaseOrder, "tevkifat_rate"), "PurchaseOrder must have tevkifat_rate"
    assert hasattr(PurchaseOrder, "tevkifat_amount"), "PurchaseOrder must have tevkifat_amount"
    assert hasattr(PurchaseOrder, "total_amount"), "PurchaseOrder must have total_amount"
    assert hasattr(PurchaseOrder, "currency"), "PurchaseOrder must have currency"
    print(" [PASS] Test 1: PurchaseOrder model has all fiscal, KDV, and Tevkifat columns.")

    # ۲. تست محاسبه مالیات عمومی ترکیه بدون توقیف (مثلاً اوره یا اقلام غیر فولادی)
    res_tr_gen = TaxService.calculate_tax(
        base_amount=100000.0,
        region_code="TR",
        is_steel=False
    )
    assert res_tr_gen.base_amount == 100000.0
    assert res_tr_gen.vat_rate == 0.20
    assert res_tr_gen.vat_amount == 20000.0
    assert res_tr_gen.has_tevkifat is False
    assert res_tr_gen.tevkifat_amount == 0.0
    assert res_tr_gen.payable_vat == 20000.0
    assert res_tr_gen.total_payable == 120000.0
    assert res_tr_gen.buyer_tax_liability == 0.0
    assert res_tr_gen.currency_symbol == "₺"
    print(" [PASS] Test 2: Standard Turkish KDV (20%) calculation verified.")

    # ۳. تست محاسبه تخصصی توقیف ارزش افزوده آهن و فولاد ترکیه (Demir-Çelik Tevkifatı 4/10)
    # طبق فرمول رسمی اداره مالیات ترکیه (GİB):
    # پایه = ۱۰۰,۰۰۰ لیر
    # کل ارزش افزوده (۲۰٪) = ۲۰,۰۰۰ لیر
    # کسر توقیف ۴/۱۰ = ۸,۰۰۰ لیر (تعهد خریدار در اظهارنامه فرم ۲ مالیات)
    # ارزش افزوده قابل پرداخت به فروشنده ۶/۱۰ = ۱۲,۰۰۰ لیر
    # کل مبلغ پرداختی خریدار به فروشنده = ۱۰۰,۰۰۰ + ۱۲,۰۰۰ = ۱۱۲,۰۰۰ لیر
    res_tr_steel = TaxService.calculate_tax(
        base_amount=100000.0,
        region_code="TR",
        is_steel=True,
        tevkifat_ratio="4/10"
    )
    assert res_tr_steel.base_amount == 100000.0
    assert res_tr_steel.vat_rate == 0.20
    assert res_tr_steel.vat_amount == 20000.0
    assert res_tr_steel.has_tevkifat is True
    assert res_tr_steel.tevkifat_rate_str == "4/10"
    assert res_tr_steel.tevkifat_numerator == 4
    assert res_tr_steel.tevkifat_denominator == 10
    assert res_tr_steel.tevkifat_amount == 8000.0
    assert res_tr_steel.payable_vat == 12000.0
    assert res_tr_steel.total_payable == 112000.0
    assert res_tr_steel.buyer_tax_liability == 8000.0
    print(" [PASS] Test 3: Turkish Demir-Çelik Tevkifatı (4/10 withholding) formula 100% verified.")

    # ۴. تست تشخیص خودکار مشمولیت توقیف آهن‌آلات (GTİP کدهای فصل ۷۲ و ۷۳ و دسته‌ها)
    assert TaxService.is_steel_tevkifat_eligible(gtip_code="7214.20.00.00.00") is True
    assert TaxService.is_steel_tevkifat_eligible(gtip_code="7207.11.14.00.00") is True
    assert TaxService.is_steel_tevkifat_eligible(gtip_code="7306.61.10.00.00") is True
    assert TaxService.is_steel_tevkifat_eligible(category_code="STL-RAW") is True
    assert TaxService.is_steel_tevkifat_eligible(product_name="Nervürlü Çelik Kütük 150") is True
    
    # موارد غیر فولادی و کود شیمیایی نباید مشمول توقیف شوند
    assert TaxService.is_steel_tevkifat_eligible(gtip_code="3102.10.10.00.00") is False
    assert TaxService.is_steel_tevkifat_eligible(product_name="Granül Üre Gübresi %46") is False
    print(" [PASS] Test 4: Automatic GTİP / Product steel classification for tevkifat verified.")

    # ۵. تست تضمین عدم پس‌رفت مالیات در نسخه ایران (۱۰٪ ارزش افزوده بدون توقیف)
    res_ir = TaxService.calculate_tax(
        base_amount=100000000.0,
        region_code="IR",
        is_steel=True  # در ایران توقیف نوع ترکیه وجود ندارد
    )
    assert res_ir.base_amount == 100000000.0
    assert res_ir.vat_rate == 0.10
    assert res_ir.vat_amount == 10000000.0
    assert res_ir.has_tevkifat is False
    assert res_ir.tevkifat_amount == 0.0
    assert res_ir.total_payable == 110000000.0
    assert res_ir.currency_symbol == "ریال"
    print(" [PASS] Test 5: Zero-Regression: Iranian standard 10% VAT verified.")

    # ۶. تست پایگاه‌داده و ثبت سفارش خرید واقعی با موتور مالیاتی
    test_db_url = "sqlite:///./test_part4.db"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    try:
        sup_tr = Supplier(name="İsdemir Demir Çelik", code="TR-TEST-SUP", country_code="TR", vkn="4810052415")
        prod_reb = Product(name="Nervürlü İnşaat Demiri Ø16mm", uom="kg", sku="TR-TEST-REB", gtip_code="7214.20.00.00.00")
        db.add_all([sup_tr, prod_reb])
        db.commit()

        # ثبت سفارش خرید ترکیه مشمول توقیف ۴/۱۰
        po_tr = PurchaseOrder(
            po_number="PO-TR-TEST-001",
            supplier_id=sup_tr.id,
            subtotal_amount=res_tr_steel.base_amount,
            vat_rate=res_tr_steel.vat_rate,
            vat_amount=res_tr_steel.vat_amount,
            tevkifat_rate=res_tr_steel.tevkifat_rate_str,
            tevkifat_amount=res_tr_steel.tevkifat_amount,
            total_amount=res_tr_steel.total_payable,
            currency="TRY"
        )
        db.add(po_tr)
        db.commit()

        q_po = db.query(PurchaseOrder).filter_by(po_number="PO-TR-TEST-001").first()
        assert q_po is not None
        assert q_po.subtotal_amount == 100000.0
        assert q_po.vat_amount == 20000.0
        assert q_po.tevkifat_amount == 8000.0
        assert q_po.total_amount == 112000.0
        assert q_po.currency == "TRY"
        print(" [PASS] Test 6: Database ORM persistence for PurchaseOrder with Tevkifat passed.")

        # ۷. تست رندر قالب purchase_detail.html
        env = Environment(loader=FileSystemLoader("templates"))
        tmpl = env.get_template("purchase_detail.html")

        # رندر نسخه ترکیه با جعبه توقیف مالیات
        req_tr = make_request("TR")
        html_tr = tmpl.render(
            request=req_tr,
            order=q_po,
            warehouses=[],
            total_amount=res_tr_steel.total_payable,
            tax_info=res_tr_steel,
            is_tr=True
        )
        assert "Matrah (Net Tutar):" in html_tr
        assert "Hesaplanan KDV (%20):" in html_tr
        assert "Demir-Çelik Tevkifatı (4/10):" in html_tr
        assert "-8,000.00 ₺" in html_tr
        assert "Tahsil Edilecek KDV:" in html_tr
        assert "Toplam Ödenecek:" in html_tr
        assert "112,000.00 ₺" in html_tr
        print(" [PASS] Test 7: purchase_detail.html renders Turkish fiscal box with 4/10 Tevkifat cleanly.")

        # رندر نسخه ایران با مالیات ۱۰٪ استاندارد
        req_ir = make_request("IR")
        html_ir = tmpl.render(
            request=req_ir,
            order=q_po,
            warehouses=[],
            total_amount=res_ir.total_payable,
            tax_info=res_ir,
            is_tr=False
        )
        assert "مبلغ خالص پایه:" in html_ir
        assert "مالیات بر ارزش افزوده" in html_ir
        assert "Demir-Çelik Tevkifatı" not in html_ir
        assert "مبلغ نهایی فاکتور:" in html_ir
        print(" [PASS] Test 8: Zero-Regression: purchase_detail.html renders Iranian VAT correctly.")

    finally:
        db.close()
        engine.dispose()
        if os.path.exists("./test_part4.db"):
            try:
                os.remove("./test_part4.db")
            except Exception:
                pass

    print("==================================================")
    print("ALL 8 TESTS PASSED FOR PART 4 SUCCESSFULLY! (100%)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
