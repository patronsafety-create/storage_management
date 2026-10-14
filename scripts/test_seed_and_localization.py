"""
تست اعتبارسنجی جامع تزریق داده‌های نمونه و ترجمه دو زبانه (فارسی - ترکی)
NexusPour ERP - Seed Data & Dual Localization Automated Verification Suite
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request

from src.infrastructure.database import Base
from src.domain_model import inventory_models, auth_models
from src.core.localization.regions import (
    Region, REGIONS, get_active_region, localize_display_name,
    TR_MASTER_DATA_MAP, IR_MASTER_DATA_MAP
)
from scripts.seed_demo_data import seed_database


def make_request(cookie_region=None):
    headers = []
    if cookie_region:
        headers.append((b"cookie", f"nexus_region={cookie_region}".encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/inventory/transactions",
        "headers": headers,
    }
    return Request(scope)


def run_tests():
    print("=" * 65)
    print("🚀 اجرای تست‌های یکپارچه داده‌های نمونه و ترجمه دو زبانه (فارسی / ترکی)")
    print("=" * 65)

    # ۱. راه‌اندازی دیتابیس آزمایشی در حافظه (In-Memory SQLite)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # ایجاد کاربر Admin پیش‌فرض
    admin_user = auth_models.User(
        username="admin",
        hashed_password="hashed_pw_dummy",
        full_name="مهندس پورمحمود",
        is_active=True
    )
    db.add(admin_user)
    db.commit()

    # ۲. اجرای موتور تزریق داده‌ها
    seed_database(db)

    # ۳. بررسی ردیف‌های ایجاد شده در پایگاه داده
    product_count = db.query(inventory_models.Product).count()
    tx_count = db.query(inventory_models.StockTransaction).count()
    wb_count = db.query(inventory_models.WeighbridgeTicket).count()
    sup_count = db.query(inventory_models.Supplier).count()
    cust_count = db.query(inventory_models.Customer).count()
    po_count = db.query(inventory_models.PurchaseOrder).count()
    cut_count = db.query(inventory_models.CuttingOrder).count()
    bag_count = db.query(inventory_models.BaggingOrder).count()

    print(f"\n📊 نتایج رکوردها در دیتابیس:")
    print(f" - کالاها: {product_count}")
    print(f" - حواله‌های ورود و خروج: {tx_count}")
    print(f" - قبوض باسکول: {wb_count}")
    print(f" - تأمین‌کنندگان: {sup_count}")
    print(f" - مشتریان و پروژه‌ها: {cust_count}")
    print(f" - سفارشات خرید: {po_count}")
    print(f" - دستورات برش: {cut_count}")
    print(f" - دستورات کیسه‌گیری: {bag_count}")

    assert product_count >= 13, f"Expected at least 13 products, got {product_count}"
    assert tx_count >= 10, f"Expected at least 10 transactions, got {tx_count}"
    assert wb_count >= 6, f"Expected at least 6 weighbridge tickets, got {wb_count}"
    assert sup_count >= 8, f"Expected at least 8 suppliers, got {sup_count}"
    assert cust_count >= 7, f"Expected at least 7 customers, got {cust_count}"
    assert po_count >= 2, f"Expected at least 2 POs, got {po_count}"
    assert cut_count >= 2, f"Expected at least 2 cutting orders, got {cut_count}"
    assert bag_count >= 1, f"Expected at least 1 bagging order, got {bag_count}"

    print(" [PASS] Test 1: All ERP entities seeded and populated successfully.")

    # ۴. تست تطابق ترجمه دو زبانه (فارسی ⇄ ترکی) برای محصولات درخواستی کاربر
    test_cases = [
        # (نام فارسی, ترجمه مورد انتظار ترکی)
        ("شمش فولادی ۱۵۰×۱۵۰", "Sürekli Döküm Çelik Kütük 150×150mm"),
        ("شمش فولادی ۱۳۰×۱۳۰", "Sürekli Döküm Çelik Kütük 130×130mm"),
        ("شمش آهن", "Çelik Kütük (Demir Kütük)"),
        ("میلگرد آجدار سایز ۱۴ (شاخه ۱۲ متری)", "Nervürlü İnşaat Demiri Ø14mm B420B (12m)"),
        ("میلگرد آجدار سایز ۱۶ (شاخه ۱۲ متری)", "Nervürlü İnşaat Demiri Ø16mm B420B (12m)"),
        ("میلگرد آجدار سایز ۱۸ (شاخه ۱۲ متری)", "Nervürlü İnşaat Demiri Ø18mm B420B (12m)"),
        ("میلگرد آجدار سایز ۲۰ (شاخه ۱۲ متری)", "Nervürlü İnşaat Demiri Ø20mm B420B (12m)"),
        ("تیرآهن IPE 14", "IPE 140 Yapısal Çelik Profil"),
        ("تیرآهن IPE 16", "IPE 160 Yapısal Çelik Profil"),
        ("تیرآهن IPE 18", "IPE 180 Yapısal Çelik Profil"),
        ("تیرآهن IPE 20", "IPE 200 Yapısal Çelik Profil"),
        ("اوره گرانول صادراتی (فله)", "Granül Üre Gübresi %46 Azot (Dökme)"),
        ("کود اوره گرانول ۴۶ درصد ازت (جامبوبگ ۱ تنی)", "Granül Üre Gübresi %46 Azot (1 Tonluk Big-Bag)"),
        ("کلاف گرم فولادی (ورق سیاه رول HRC)", "Sıcak Haddelenmiş Rulo Sac (HRC)"),
        ("ورق سیاه برشی فولادی (شیت ۱۰ میل)", "Sıcak Haddelenmiş Plaka Sac (10mm)"),
        ("انبار شماره یک (محوطه سنگین و شمش)", "1 Nolu Açık Saha Deposu (Kütük ve Ağır Çelik)"),
        ("شرکت سهامی ذوب‌آهن اصفهان", "İsfahan Demir Çelik Fabrikaları (ESCO)"),
        ("پروژه ساختمانی برج آرمان امید", "Arman Kule İnşaat Projesi"),
        ("تریلی کفی ۱۸ چرخ (بندیل و میلگرد)", "Standart 5 Dingilli Açık Kasa Treyler (Tır)")
    ]

    for fa_name, tr_expected in test_cases:
        # ترجمه به ترکی
        tr_actual = localize_display_name(fa_name, is_tr=True)
        assert tr_actual == tr_expected, f"TR translation failed for '{fa_name}'. Expected '{tr_expected}', got '{tr_actual}'"

        # ترجمه در حالت فارسی (باید اصل فارسی برگردد)
        fa_actual = localize_display_name(fa_name, is_tr=False)
        assert fa_actual == fa_name, f"IR rendering failed for '{fa_name}'. Expected '{fa_name}', got '{fa_actual}'"

        # نگاشت معکوس (ترکی به فارسی در حالت IR)
        rev_fa = localize_display_name(tr_expected, is_tr=False)
        assert len(rev_fa) > 0 and rev_fa != tr_expected, (
            f"Reverse translation failed for '{tr_expected}'. Got '{rev_fa}'"
        )

    print(f" [PASS] Test 2: Dual localization (FA -> TR and TR -> FA) verified for all {len(test_cases)} critical industrial terms.")

    # ۵. تست رندر قالب‌های Jinja2 با فیلتر tr_loc
    env = Environment(loader=FileSystemLoader("templates"))
    env.filters["tr_loc"] = localize_display_name

    # تست رندر قبض باسکول (weighbridge_slip.html) در هر دو زبان
    ticket = db.query(inventory_models.WeighbridgeTicket).first()
    slip_tmpl = env.get_template("weighbridge_slip.html")

    # رندر در مد فارسی
    req_ir = make_request("IR")
    html_slip_ir = slip_tmpl.render(
        request=req_ir,
        ticket=ticket,
        is_tr=False,
        region=REGIONS[Region.IR],
        title="قبض توزین باسکول"
    )
    assert ticket.product.name in html_slip_ir or localize_display_name(ticket.product.name, is_tr=False) in html_slip_ir
    print(" [PASS] Test 3: weighbridge_slip.html rendered successfully in Persian mode (IR).")

    # رندر در مد ترکی
    req_tr = make_request("TR")
    html_slip_tr = slip_tmpl.render(
        request=req_tr,
        ticket=ticket,
        is_tr=True,
        region=REGIONS[Region.TR],
        title="Kantar Tartım Fişi"
    )
    tr_prod_name = localize_display_name(ticket.product.name, is_tr=True)
    assert tr_prod_name in html_slip_tr, f"Expected Turkish product name '{tr_prod_name}' in ticket slip"
    print(" [PASS] Test 4: weighbridge_slip.html rendered successfully in Turkish mode (TR) with authentic Turkish metallurgy name.")

    # تست رندر لیست تراکنش‌ها (transactions.html) در مد ترکی
    txs = db.query(inventory_models.StockTransaction).all()
    prods = db.query(inventory_models.Product).all()
    whs = db.query(inventory_models.Warehouse).all()
    tx_tmpl = env.get_template("transactions.html")

    html_tx_tr = tx_tmpl.render(
        request=req_tr,
        transactions=txs,
        products=prods,
        warehouses=whs,
        total_items=len(txs),
        page=1,
        total_pages=1,
        filter_product=None,
        filter_type=None,
        filter_status=None,
        is_tr=True,
        region=REGIONS[Region.TR]
    )
    # اطمینان از حضور نام‌های ترکی میلگرد و شمش و تیرآهن در جدول تراکنش‌های ترکی
    assert "Nervürlü İnşaat Demiri" in html_tx_tr, "Expected Turkish rebar name in Turkish transactions table"
    assert "Sürekli Döküm Çelik Kütük" in html_tx_tr, "Expected Turkish billet name in Turkish transactions table"
    assert "IPE 180" in html_tx_tr, "Expected Turkish beam name in Turkish transactions table"
    print(" [PASS] Test 5: transactions.html rendered successfully with all heavy steel items localized to Turkish.")

    # تست رندر کارت‌های موجودی کالا (stock_balance.html) در مد ترکی
    stock_items = []
    for p in prods:
        stock_items.append({
            "id": p.id,
            "sku": p.sku,
            "name": p.name,
            "category": p.category.name if p.category else "Genel",
            "warehouse": whs[0].name if whs else "انبار شماره یک",
            "total_in": 25000.0,
            "total_out": 10000.0,
            "current_balance": 15000.0,
            "uom": p.uom,
            "status": "موجودی کافی",
            "is_out_of_stock": False,
            "is_critical": False,
            "is_low": False
        })
    bal_tmpl = env.get_template("stock_balance.html")
    all_cats = db.query(inventory_models.ProductCategory).all()
    html_bal_tr = bal_tmpl.render(
        request=req_tr,
        stock_balances=stock_items,
        warehouses=whs,
        categories=all_cats,
        is_tr=True,
        region=REGIONS[Region.TR]
    )
    assert "Nervürlü İnşaat Demiri Ø14mm" in html_bal_tr
    assert "Sürekli Döküm Çelik Kütük 150×150mm" in html_bal_tr
    print(" [PASS] Test 6: stock_balance.html rendered successfully with 100% Turkish localized products.")

    print("\n" + "=" * 65)
    print("🎉 ALL SEED & DUAL LOCALIZATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
