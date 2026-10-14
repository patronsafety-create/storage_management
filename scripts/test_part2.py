import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.localization.tr_rules import (
    validate_vkn, validate_tc_kimlik, validate_turkish_phone, validate_turkish_party_data
)
from src.core.localization.regions import REGIONS, get_active_region
from src.infrastructure.database import Base
from src.domain_model.inventory_models import Supplier, Customer

def make_request(cookie_region=None):
    headers = []
    if cookie_region:
        headers.append((b"cookie", f"nexus_region={cookie_region}".encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/master-data/parties",
        "headers": headers,
    }
    return Request(scope)

def run_tests():
    print("==================================================")
    print("Running Part 2 Tests: Turkish Business Partners & VKN")
    print("==================================================")

    # 1. Test VKN Official Checksum Algorithm (GİB)
    assert validate_vkn("3530018590") == True, "Erdemir VKN should be valid"
    assert validate_vkn("4810052415") == True, "İsdemir VKN should be valid"
    assert validate_vkn("5240031891") == True, "Kardemir VKN should be valid"
    assert validate_vkn("8510041233") == True, "Toros Gübre VKN should be valid"
    assert validate_vkn("7350021940") == True, "Rönesans VKN should be valid"
    assert validate_vkn("3360018422") == True, "ENKA VKN should be valid"
    assert validate_vkn("6120048192") == True, "Marmara Çelik VKN should be valid"
    assert validate_vkn("1111111111") == False, "Invalid VKN 1111111111 must fail checksum"
    assert validate_vkn("1234567891") == False, "Invalid VKN 1234567891 must fail checksum"
    assert validate_vkn("") == False
    assert validate_vkn("abc") == False
    print(" [PASS] Test 1: VKN official GİB checksum validation passed for all major Turkish industrial firms.")

    # 2. Test Turkish Phone Validation
    assert validate_turkish_phone("05321234567") == True
    assert validate_turkish_phone("02123365000") == True
    assert validate_turkish_phone("+905321234567") == True
    assert validate_turkish_phone("5321234567") == True
    assert validate_turkish_phone("01234567890") == False
    assert validate_turkish_phone("12345") == False
    print(" [PASS] Test 2: Turkish mobile and landline phone validation passed.")

    # 3. Test validate_turkish_party_data
    err, name, phone, vkn = validate_turkish_party_data(
        "Ereğli Demir ve Çelik Fabrikaları T.A.Ş.", "03723232500", "3530018590", "Tedarikçi"
    )
    assert err is None, f"Expected no error, got: {err}"
    assert vkn == "3530018590"

    err, _, _, _ = validate_turkish_party_data("Sahte Firma", "05321234567", "1111111111", "Tedarikçi")
    assert err is not None, "Invalid VKN checksum must return error"
    print(" [PASS] Test 3: validate_turkish_party_data error reporting passed.")

    # 4. In-Memory SQLite Test of Models & Search
    sqlite_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=sqlite_engine)
    TestSession = sessionmaker(bind=sqlite_engine)
    db = TestSession()

    try:
        # Create Turkish Supplier
        s_tr = Supplier(
            name="Ereğli Demir ve Çelik Fabrikaları T.A.Ş. (Erdemir)",
            code="TR-SUP-001",
            contact_person="Ahmet Yılmaz",
            phone="03723232500",
            email="satis@erdemir.com.tr",
            address="Kdz. Ereğli, Zonguldak, Türkiye",
            national_id="3530018590",
            vkn="3530018590",
            tax_office="Karadeniz Ereğli Vergi Dairesi",
            mersis_no="0353001859000018",
            country_code="TR",
            is_active=True
        )
        # Create Iranian Supplier
        s_ir = Supplier(
            name="شرکت سهامی ذوب‌آهن اصفهان",
            code="SUP-002",
            contact_person="مهندس رضایی",
            phone="09121234567",
            email="info@esco.ir",
            address="اصفهان",
            national_id="10260087451",
            country_code="IR",
            is_active=True
        )
        db.add_all([s_tr, s_ir])

        # Create Turkish Customer
        c_tr = Customer(
            name="ENKA İnşaat ve Sanayi A.Ş.",
            code="TR-CUST-002",
            contact_person="Hakan Arslan",
            phone="02123761000",
            email="procurement@enka.com",
            address="Beşiktaş, İstanbul",
            national_id="3360018422",
            vkn="3360018422",
            tax_office="Beşiktaş Vergi Dairesi",
            mersis_no="0336001842200014",
            country_code="TR",
            credit_limit=25000000.0,
            is_active=True
        )
        db.add(c_tr)
        db.commit()

        # Query & Search Tests
        found_by_vkn = db.query(Supplier).filter(Supplier.vkn == "3530018590").first()
        assert found_by_vkn is not None and "Erdemir" in found_by_vkn.name
        print(f" [PASS] Test 4: Database query by VKN succeeded: {found_by_vkn.name}")

        found_by_office = db.query(Customer).filter(Customer.tax_office.ilike("%Beşiktaş%")).first()
        assert found_by_office is not None and "ENKA" in found_by_office.name
        print(f" [PASS] Test 5: Database query by Tax Office succeeded: {found_by_office.name}")

        # Zero regression on Iranian supplier
        found_ir = db.query(Supplier).filter(Supplier.code == "SUP-002").first()
        assert found_ir.country_code == "IR"
        assert found_ir.national_id == "10260087451"
        assert found_ir.vkn is None
        print(" [PASS] Test 6: Zero-regression verified for Iranian party data.")

        # 5. Template Rendering Test
        env = Environment(loader=FileSystemLoader("templates"))
        template = env.get_template("parties.html")

        # Test render with TR region
        req_tr = make_request("TR")
        reg_tr = get_active_region(req_tr)
        rendered_tr = template.render(
            request=req_tr,
            user=None,
            current_user=None,
            is_admin=True,
            suppliers=[{"party": s_tr, "tx_count": 3, "total_qty": 450.0, "total_value": 9000000.0}],
            customers=[{"party": c_tr, "tx_count": 2, "total_qty": 200.0, "total_value": 4000000.0}],
            stats={"total_suppliers": 1, "total_customers": 1, "total_inbound_txs": 3, "total_outbound_txs": 2},
            active_tab="suppliers",
            search="",
            status_filter="all",
            msg=None,
            error=None,
            active_region=reg_tr,
            active_region_code="TR",
            is_tr=True
        )
        assert "🇹🇷 TR" in rendered_tr, "TR flag badge should appear"
        assert "3530018590" in rendered_tr, "Erdemir VKN should appear in table"
        assert "Karadeniz Ereğli" in rendered_tr, "Tax office should appear in table"
        assert "Vergi No / VKN" in rendered_tr, "Turkish header should appear"
        assert "name=\"country_code\"" in rendered_tr, "Country selector must appear in modal"
        assert "name=\"vkn\"" in rendered_tr, "VKN input must appear in modal"
        print(" [PASS] Test 7: Template rendering in TR mode verified with VKN badges and Turkish labels.")

        # Test render with IR region
        req_ir = make_request("IR")
        reg_ir = get_active_region(req_ir)
        rendered_ir = template.render(
            request=req_ir,
            user=None,
            current_user=None,
            is_admin=True,
            suppliers=[{"party": s_ir, "tx_count": 5, "total_qty": 1200.0, "total_value": 1500000000.0}],
            customers=[],
            stats={"total_suppliers": 1, "total_customers": 0, "total_inbound_txs": 5, "total_outbound_txs": 0},
            active_tab="suppliers",
            search="",
            status_filter="all",
            msg=None,
            error=None,
            active_region=reg_ir,
            active_region_code="IR",
            is_tr=False
        )
        assert "🇮🇷 IR" in rendered_ir, "IR flag badge should appear"
        assert "10260087451" in rendered_ir, "Iranian national ID should appear"
        print(" [PASS] Test 8: Template rendering in IR mode verified with Iran national ID and labels.")

    finally:
        db.close()

    print("==================================================")
    print(" ALL PART 2 TESTS PASSED SUCCESSFULLY! (100%)")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
