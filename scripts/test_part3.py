import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.infrastructure.database import Base
from src.domain_model.inventory_models import Product, ProductCategory, Warehouse
from src.schemas import ProductBase
from src.core.localization.tr_rules import validate_gtip, format_gtip
from src.core.localization.regions import REGIONS, get_active_region

def make_request(cookie_region=None):
    headers = []
    if cookie_region:
        headers.append((b"cookie", f"nexus_region={cookie_region}".encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/master-data/products",
        "headers": headers,
    }
    return Request(scope)

def run_tests():
    print("==================================================")
    print("Running Part 3 Tests: Turkish GTİP & TSE Metallurgy Standards")
    print("==================================================")

    # ۱. تست مدل Product: وجود ستون‌های gtip_code و tse_standard
    assert hasattr(Product, "gtip_code"), "Product model must have 'gtip_code' attribute"
    assert hasattr(Product, "tse_standard"), "Product model must have 'tse_standard' attribute"
    print(" [PASS] Test 1: Product model has gtip_code and tse_standard columns.")

    # ۲. تست اسکیمای Pydantic ProductBase
    schema_fields = ProductBase.model_fields
    assert "gtip_code" in schema_fields, "ProductBase schema must have 'gtip_code'"
    assert "tse_standard" in schema_fields, "ProductBase schema must have 'tse_standard'"
    print(" [PASS] Test 2: ProductBase Pydantic schema includes gtip_code and tse_standard fields.")

    # ۳. تست اعتبارسنجی الگوریتم کدهای ۱۲ رقمی تعرفه گمرکی ترکیه (GTİP)
    assert validate_gtip("7214.20.00.00.00") is True, "Dotted 12-digit rebar GTİP must be valid"
    assert validate_gtip("721420000000") is True, "Raw 12-digit rebar GTİP must be valid"
    assert validate_gtip("7207.11.14.00.00") is True, "Billet GTİP must be valid"
    assert validate_gtip("3102.10.10.00.00") is True, "Urea fertilizer GTİP must be valid"
    assert validate_gtip("7306.61.10.00.00") is True, "Steel pipe GTİP must be valid"

    assert validate_gtip("721420") is False, "6-digit HS code is not full 12-digit GTİP"
    assert validate_gtip("7214200000001") is False, "13-digit code must be invalid"
    assert validate_gtip("7214ABCD0000") is False, "Alphanumeric GTİP must be invalid"
    assert validate_gtip("") is False, "Empty GTİP must be invalid"
    assert validate_gtip(None) is False, "None GTİP must be invalid"
    print(" [PASS] Test 3: Official 12-digit GTİP customs code validation logic verified.")

    # ۴. تست فرمت‌بندی استاندارد نقطه‌گذاری رسمی GTİP
    assert format_gtip("721420000000") == "7214.20.00.00.00", "Must format rebar GTİP correctly"
    assert format_gtip("310210100000") == "3102.10.10.00.00", "Must format urea GTİP correctly"
    assert format_gtip("720711140000") == "7207.11.14.00.00", "Must format billet GTİP correctly"
    print(" [PASS] Test 4: GTİP standard 12-digit dotted formatting verified (XXXX.XX.XX.XX.XX).")

    # ۵. تست پایگاه‌داده و چرخه حیات (DB Session, Seeding & CRUD)
    test_db_url = "sqlite:///./test_part3.db"
    engine = create_engine(test_db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    try:
        # درج دسته‌بندی و کالای نمونه متالورژی و شیمیایی با استانداردهای ترکیه
        cat_steel = ProductCategory(name="مقاطع و شمش فولادی", code="STL-RAW")
        cat_chem = ProductCategory(name="مواد شیمیایی و پتروشیمی", code="CHEM-PET")
        db.add_all([cat_steel, cat_chem])
        db.commit()

        p_rebar = Product(
            name="Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
            uom="kg",
            secondary_uom="çubuk",
            nominal_weight=18.96,
            sku="TR-REB-B420B-16",
            gtip_code="7214.20.00.00.00",
            tse_standard="TS 708",
            hs_code="72142000",
            category_id=cat_steel.id,
            brand="İsdemir",
            size="16",
            length=12.0,
            grade="B420B",
            standard="TS 708 / TS EN 10080",
            min_stock=5000.0,
            reorder_point=10000.0
        )
        p_billet = Product(
            name="Sürekli Döküm Çelik Kütük 150×150mm S235JR",
            uom="ton",
            secondary_uom="kütük",
            nominal_weight=2000.0,
            sku="TR-BLT-150-S235JR",
            gtip_code="7207.11.14.00.00",
            tse_standard="TS EN 10025-2",
            hs_code="72071114",
            category_id=cat_steel.id,
            brand="Kardemir",
            size="150x150",
            length=6.0,
            grade="S235JR",
            standard="TS EN 10025-2",
            min_stock=100.0,
            reorder_point=200.0
        )
        p_urea = Product(
            name="Granül Üre Gübresi %46 Azot (Dökme & Big Bag)",
            uom="ton",
            secondary_uom="big-bag",
            nominal_weight=1000.0,
            sku="TR-UREA-GRAN-46",
            gtip_code="3102.10.10.00.00",
            tse_standard="TS 3601",
            hs_code="31021010",
            category_id=cat_chem.id,
            brand="Toros Gübre",
            grade="%46 N",
            standard="TS 3601 / EC FERTILIZER",
            min_stock=50.0,
            reorder_point=100.0
        )
        db.add_all([p_rebar, p_billet, p_urea])
        db.commit()

        # استعلام و راستی‌آزمایی کالاهای ثبت‌شده
        q_rebar = db.query(Product).filter_by(sku="TR-REB-B420B-16").first()
        assert q_rebar is not None
        assert q_rebar.gtip_code == "7214.20.00.00.00"
        assert q_rebar.tse_standard == "TS 708"
        assert q_rebar.grade == "B420B"

        q_billet = db.query(Product).filter_by(sku="TR-BLT-150-S235JR").first()
        assert q_billet is not None
        assert q_billet.gtip_code == "7207.11.14.00.00"
        assert q_billet.tse_standard == "TS EN 10025-2"

        q_urea = db.query(Product).filter_by(sku="TR-UREA-GRAN-46").first()
        assert q_urea is not None
        assert q_urea.gtip_code == "3102.10.10.00.00"
        assert q_urea.tse_standard == "TS 3601"

        print(" [PASS] Test 5: Database ORM persistence for Turkish steel and chemical demo products with GTİP & TSE passed.")

        # ۶. تست قالب‌ها: products.html و barcode_label.html
        env = Environment(loader=FileSystemLoader("templates"))
        
        # بررسی کدها در products.html
        with open("templates/products.html", "r", encoding="utf-8") as f:
            products_html = f.read()
        assert "gtip_code" in products_html, "products.html must contain gtip_code"
        assert "tse_standard" in products_html, "products.html must contain tse_standard"
        assert "edit_gtip_code" in products_html, "products.html must contain edit_gtip_code id"
        assert "edit_tse_standard" in products_html, "products.html must contain edit_tse_standard id"
        assert "/label" in products_html, "products.html must have barcode label print link"
        print(" [PASS] Test 6: products.html template correctly includes GTİP & TSE inputs, table badges and print link.")

        # بررسی رندر barcode_label.html برای منطقه ترکیه
        req_tr = make_request("TR")
        label_tmpl = env.get_template("barcode_label.html")
        rendered_label_tr = label_tmpl.render(request=req_tr, product=q_rebar)
        assert "NexusPour ERP Türkiye" in rendered_label_tr
        assert "GTİP:" in rendered_label_tr
        assert "7214.20.00.00.00" in rendered_label_tr
        assert "TS 708" in rendered_label_tr
        assert "Gümrük & TSE Kalite Onaylı" in rendered_label_tr
        print(" [PASS] Test 7: barcode_label.html renders Turkish metallurgy label with GTİP & TSE standards.")

        # بررسی رندر barcode_label.html برای منطقه ایران (تضمین عدم پس‌رفت)
        p_iran = Product(
            name="میلگرد آجدار سایز ۱۶ نیشابور",
            uom="کیلوگرم",
            sku="REB-A3-16-NSB",
            irc_code="2800000140303",
            brand="فولاد نیشابور",
            size="16",
            grade="A3",
            standard="DIN 488"
        )
        req_ir = make_request("IR")
        rendered_label_ir = label_tmpl.render(request=req_ir, product=p_iran)
        assert "نکسوس‌پـور ERP" in rendered_label_ir
        assert "شناسه تجارت IRC: 2800000140303" in rendered_label_ir
        assert "مالکیت: امید پورمحمود" in rendered_label_ir
        print(" [PASS] Test 8: Zero Regression: barcode_label.html renders Iranian IRC standard correctly.")

    finally:
        db.close()
        engine.dispose()
        if os.path.exists("./test_part3.db"):
            try:
                os.remove("./test_part3.db")
            except Exception:
                pass

    print("==================================================")
    print("ALL 8 TESTS PASSED FOR PART 3 SUCCESSFULLY! (100%)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
