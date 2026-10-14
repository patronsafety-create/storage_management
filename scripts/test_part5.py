"""
NexusPour ERP - Test Suite for Part 5 (Turkey Localization: Weighbridge, Plate Format, KGM Limits & Complete Persian Removal)
Owner & Architect: Omid Pourmahmoud
"""
import sys
import os
import re
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request

from src.core.localization.regions import (
    localize_display_name,
    get_active_region,
    TR_MASTER_DATA_MAP,
    REGIONS,
    Region
)
from src.core.localization.tr_rules import (
    validate_turkish_plate,
    format_turkish_plate,
    check_kgm_weight_limit,
    KGM_TRUCK_LIMITS,
)

def run_tests():
    print("==================================================")
    print("Running Part 5 Tests: Turkish Weighbridge, Plates & Localization")
    print("==================================================")

    # -----------------------------------------------------------------
    # ۱. تست اعتبارسنجی و فرمت‌بندی پلاک‌های استاندارد جمهوری ترکیه
    # -----------------------------------------------------------------
    valid_plates = [
        "34 ABC 123",
        "06 TR 9876",
        "35 A 4567",
        "16 AB 345",
        "01 BAA 12",
        "81 DZC 999",
        "34abc123",
        " 06  TR 9876 ",
    ]
    for plate in valid_plates:
        is_val = validate_turkish_plate(plate)
        assert is_val is True, f"Plate {plate} should be valid"
        clean = format_turkish_plate(plate)
        assert clean == clean.upper(), f"Formatted plate {clean} must be uppercase"
        province = int(clean[:2])
        assert 1 <= province <= 81, f"Province {province} must be between 01 and 81"

    invalid_plates = [
        "00 ABC 123",
        "82 ABC 123",
        "34 QWE 123",
        "34 WWW 123",
        "34 XXX 123",
        "ABC 34 123",
        "34 123 ABC",
        "12345",
    ]
    for plate in invalid_plates:
        is_val = validate_turkish_plate(plate)
        assert is_val is False, f"Plate {plate} should be invalid"

    formatted_34 = format_turkish_plate("34abc123")
    assert formatted_34 == "34 ABC 123", f"Expected '34 ABC 123', got '{formatted_34}'"
    print(" [PASS] Test 1: Turkish license plate syntax, province codes (01-81) & formatting 100% verified.")

    # -----------------------------------------------------------------
    # ۲. تست حدود قانونی تناژ باسکول تریلی براساس استانداردهای رسمی KGM ترکیه
    # -----------------------------------------------------------------
    # تریلی ۵ محوره استاندارد (۴۰ تن)
    is_over, limit, msg = check_kgm_weight_limit(39500.0, "Standart 5 Dingilli Açık Kasa Treyler (Tır)")
    assert is_over is False
    assert limit == 40000.0
    assert "Yasal Tartım Sınırları İçinde" in msg

    is_over, limit, msg = check_kgm_weight_limit(41800.0, "Standart 5 Dingilli Açık Kasa Treyler (Tır)")
    assert is_over is True
    assert limit == 40000.0
    assert "Fazla Tonaj: +1,800 kg" in msg

    # تریلی کانتینربر ۴۰ فوت (۴۴ تن)
    is_over, limit, msg = check_kgm_weight_limit(43200.0, "40 Feet Konteyner Taşıyıcı Tır (44 Ton)")
    assert is_over is False
    assert limit == 44000.0

    is_over, limit, msg = check_kgm_weight_limit(45500.0, "40 Feet Konteyner Taşıyıcı Tır (44 Ton)")
    assert is_over is True
    assert limit == 44000.0
    assert "Fazla Tonaj: +1,500 kg" in msg

    # کامیون ۴ محوره (۳۲ تن)، ۳ محوره (۲۶ تن) و ۲ محوره (۱۸ تن)
    assert check_kgm_weight_limit(31000.0, "4 Dingilli Kamyon")[0] is False
    assert check_kgm_weight_limit(33500.0, "4 Dingilli Kamyon")[0] is True
    assert check_kgm_weight_limit(27000.0, "3 Dingilli Kamyon")[0] is True
    assert check_kgm_weight_limit(19000.0, "2 Dingilli Kamyon")[0] is True

    print(" [PASS] Test 2: Karayolları Genel Müdürlüğü (KGM) 40t/44t legal truck weight limits verified.")

    # -----------------------------------------------------------------
    # ۳. تست فیلتر دیکشنری بومی‌سازی اقلام، انبارها، واحدها و دسته‌ها
    # -----------------------------------------------------------------
    assert localize_display_name("شمش فولادی ۱۵۰×۱۵۰", is_tr=True) == "Sürekli Döküm Çelik Kütük 150×150mm"
    assert localize_display_name("میلگرد آجدار سایز ۱۶ (شاخه ۱۲ متری)", is_tr=True) == "Nervürlü İnşaat Demiri Ø16mm B420B (12m)"
    assert localize_display_name("اوره گرانول صادراتی (فله)", is_tr=True) == "Granül Üre Gübresi %46 Azot (Dökme)"
    assert localize_display_name("انبار شماره یک (محوطه سنگین و شمش)", is_tr=True) == "1 Nolu Açık Saha Deposu (Kütük ve Ağır Çelik)"
    assert localize_display_name("انبار شماره دو (سوله مسقف و شیمیایی)", is_tr=True) == "2 Nolu Kapalı Depo (Kimyasal ve Gübre)"
    assert localize_display_name("انبار مرکزی", is_tr=True) == "Merkez Depo"
    assert localize_display_name("کیلوگرم", is_tr=True) == "kg"
    assert localize_display_name("تن", is_tr=True) == "ton"
    assert localize_display_name("بندیل", is_tr=True) == "bağ"
    assert localize_display_name("جامبوبگ", is_tr=True) == "big-bag"
    assert localize_display_name("مقاطع و شمش فولادی", is_tr=True) == "Çelik Kütük ve Profil Ürünleri"
    print(" [PASS] Test 3: Master data localization mapping (tr_loc) 100% verified.")

    # -----------------------------------------------------------------
    # ۴. تست بارگذاری و رندر بدون خطای قالب‌های Jinja2 در حالت ترکیه
    # -----------------------------------------------------------------
    templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "templates"))
    env = Environment(loader=FileSystemLoader(templates_dir))
    env.filters["tr_loc"] = localize_display_name

    class MockObj:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    mock_user = MockObj(
        id=1, username="admin", full_name="Omid Pourmahmoud",
        roles=[MockObj(name="Admin", description="Yönetici")]
    )
    mock_product = MockObj(
        id=1, name="شمش فولادی ۱۵۰×۱۵۰", uom="کیلوگرم", sku="STL-BILLET-150",
        description="Standard Billet", is_active=True, min_stock=100.0,
        category=MockObj(name="مقاطع و شمش فولادی")
    )
    mock_wh1 = MockObj(id=1, name="انبار شماره یک (محوطه سنگین و شمش)")
    mock_wh2 = MockObj(id=2, name="انبار شماره دو (سوله مسقف و شیمیایی)")
    mock_tx = MockObj(
        id=101, transaction_type=MockObj(value="IN"),
        product=mock_product, product_id=1,
        warehouse=mock_wh1, warehouse_id=1,
        supplier=MockObj(name="فولاد خوزستان"), customer=None,
        quantity=25000.0, unit_price=18.5, batch_number="HEAT-8841",
        reference_document="INV-2026-TR01", is_return=False,
        created_at=datetime(2026, 10, 14, 12, 30),
        created_by=mock_user,
        heat_number="HT-9921", mtc_number="MTC-2026-99"
    )

    tr_context = {
        "request": Request({"type": "http", "method": "GET", "path": "/", "headers": [(b"cookie", b"nexus_region=TR")]}),
        "is_tr": True,
        "active_region": REGIONS[Region.TR],
        "user": mock_user,
        "products": [mock_product],
        "warehouses": [mock_wh1, mock_wh2],
        "suppliers": [MockObj(id=1, name="فولاد خوزستان")],
        "customers": [MockObj(id=1, name="Özkanlar Demir Çelik")],
        "tx": mock_tx,
        "product": mock_product,
        "kardex_entries": [{"tx": mock_tx, "running_balance": 25000.0}],
        "all_products": [mock_product],
        "selected_warehouse_id": 1,
        "selected_warehouse": mock_wh1,
        "items": [{"product": mock_product, "system_stock": 25000.0}],
        "candidate_transactions": [mock_tx],
        "entries": [{
            "tx": mock_tx, "in_qty": 25000.0, "in_price": 18.5, "in_total": 462500.0,
            "out_qty": 0.0, "out_price": 0.0, "out_total": 0.0,
            "balance_qty": 25000.0, "balance_rate": 18.5, "balance_total": 462500.0
        }],
        "total_qty": 25000.0, "avg_unit_price": 18.5, "total_financial_value": 462500.0,
        "roles": [MockObj(id=1, name="Admin", description="Yönetici")],
        "users": [mock_user],
        "logs": [MockObj(
            id=1, action="CREATE", entity_name="StockTransaction", entity_id="101",
            user_name="admin", details="Giriş fişi oluşturuldu",
            created_at=datetime(2026, 10, 14, 12, 30)
        )],
        "action_filter": None, "entity_filter": None
    }

    templates_to_test = [
        "transfer_form.html",
        "return_form.html",
        "stocktaking.html",
        "kardex.html",
        "financial_kardex.html",
        "users.html",
        "audit_logs.html",
        "print_voucher.html",
    ]

    for t_name in templates_to_test:
        tmpl = env.get_template(t_name)
        rendered = tmpl.render(tr_context)
        assert len(rendered) > 100, f"Template {t_name} rendered empty output"
        print(f" [PASS] Template rendered successfully in Turkish mode: {t_name}")

    print("==================================================")
    print("ALL PART 5 AUTOMATED TESTS PASSED SUCCESSFULLY! (100%)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
