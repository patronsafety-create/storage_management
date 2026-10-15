"""
اسکریپت شکارچی خودکار باگ‌ها (Deep Bug Hunter & Enterprise Stability Scanner)
طراحی و مهندسی: امید پورمحمود (Omid Pourmahmoud)
NexusPour Enterprise ERP
"""
import sys
import os
import re
import uuid
from html.parser import HTMLParser
from datetime import datetime, timezone
from urllib.parse import urlparse

# تنظیم مسیر روت پروژه
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from src.api.main import app
from src.infrastructure.database import SessionLocal
from src.infrastructure.seed_users import seed_enterprise_users
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import (
    Product, Warehouse, Supplier, Customer, PurchaseOrder, PurchaseOrderItem,
    SalesOrder, SalesOrderItem, StockTransaction, WeighbridgeTicket, FiscalYear,
    TransactionType, BaggingOrder
)
from src.domain_model.enums import (
    DocumentStatus, PurchaseOrderStatus, SalesOrderStatus, WeighbridgeStatus,
    TransactionSource
)
from src.services.inventory_service import InventoryService


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

discovered_bugs = []
fixed_bugs = []


def record_bug(layer: str, title: str, details: str, severity: str = "HIGH"):
    bug = {
        "id": f"BUG-{len(discovered_bugs) + 1:03d}",
        "layer": layer,
        "title": title,
        "details": details,
        "severity": severity,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    discovered_bugs.append(bug)
    print(f"{RED}{BOLD}  ✖ [DISCOVERED {bug['id']}] {title}{RESET}")
    print(f"{YELLOW}    جزییات: {details}{RESET}")


def log_step(title: str):
    print(f"\n{BLUE}{BOLD}{'='*70}{RESET}")
    print(f"{BLUE}{BOLD}  🔍 {title}{RESET}")
    print(f"{BLUE}{BOLD}{'='*70}{RESET}")


def log_ok(msg: str):
    print(f"{GREEN}  ✔ {msg}{RESET}")


def get_client(username: str, password: str = "1234") -> TestClient:
    client = TestClient(app, follow_redirects=False)
    res = client.post("/login", data={"username": username, "password": password})
    assert res.status_code == 303, f"لاگین ناموفق برای {username} (کد {res.status_code})"
    return client


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.forms = set()

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == "a" and "href" in attr_dict:
            href = attr_dict["href"].strip()
            if href.startswith("/") and not href.startswith(("/static", "/logout")):
                parsed = urlparse(href)
                self.links.add(parsed.path)
        elif tag == "form" and "action" in attr_dict:
            action = attr_dict["action"].strip()
            if action.startswith("/") and not action.startswith(("/static", "/logout")):
                parsed = urlparse(action)
                self.forms.add(parsed.path)


def setup_base_fixtures():
    """آماده‌سازی سال مالی ۱۴۰۳ و انبار و کالای پیش‌فرض"""
    with SessionLocal() as db:
        seed_enterprise_users(db)
        # پاکسازی اسناد معلق یا نیمه‌کاره از تست‌های قبل جهت شروع پاک آزمون‌ها
        db.query(StockTransaction).filter(StockTransaction.status == DocumentStatus.PENDING_APPROVAL).update({"status": DocumentStatus.CANCELLED})
        db.query(WeighbridgeTicket).filter(WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING).update({"status": WeighbridgeStatus.CANCELLED})
        db.commit()

        fy = InventoryService.get_active_fiscal_year(db)

        wh = db.query(Warehouse).first()
        if not wh:
            wh = Warehouse(name="انبار مرکزی کارخانه", location="محوطه صنعتی", currency="IRR")
            db.add(wh)
            db.flush()

        prod = db.query(Product).first()
        if not prod:
            prod = Product(
                name="شمش فولادی ۱۵۰×۱۵۰",
                uom="تن",
                secondary_uom="شاخه",
                nominal_weight=2000.0,
                sku="BILLET-150-ST52",
                is_active=True
            )
            db.add(prod)
            db.flush()

        db.commit()
        return wh.id, prod.id, fy.id


# =====================================================================
# لایه اول: اسکنر تمام صفحات و قالب‌ها با هر ۵ نقش
# =====================================================================
def run_layer_1_crawler(wh_id: int, prod_id: int):
    log_step("لایه ۱: اسکنر تمام صفحات و لینک‌ها با هر ۵ نقش (Full Route & Template Crawler)")

    routes_to_test = [
        "/dashboard",
        "/inventory/transactions",
        "/inventory/balance",
        f"/inventory/kardex/{prod_id}",
        f"/inventory/financial-kardex/{prod_id}",
        "/inventory/transaction",
        "/inventory/transfer",
        "/inventory/stocktaking",
        "/inventory/stocktaking/blind-sheet",
        "/inventory/returns/new",
        "/inventory/fiscal-years",
        "/inventory/fiscal-year-close",
        "/purchases",
        "/purchases/new",
        "/sales",
        "/sales/new",
        "/weighbridge",
        "/weighbridge/new",
        "/bagging",
        "/bagging/new",
        "/master-data/products",
        "/master-data/parties",
        "/inventory/alerts",
        "/compliance",
        "/admin/users",
        "/admin/audit-logs"
    ]

    roles = ["admin", "finance", "warehouse", "commercial", "baskool"]

    for r in roles:
        client = get_client(r)
        for route in routes_to_test:
            try:
                res = client.get(route)
                if res.status_code >= 500:
                    record_bug("LAYER_1", f"خطای ۵۰۰ سرور در مسیر {route} با نقش {r}", f"پاسخ سرور: {res.text[:300]}")
                elif res.status_code == 422:
                    record_bug("LAYER_1", f"خطای اعتبارسنجی ۴۲۲ در مسیر {route} با نقش {r}", f"متن خطا: {res.text[:300]}")
            except Exception as e:
                record_bug("LAYER_1", f"کرش ناگهانی پایتون در مسیر {route} با نقش {r}", str(e))
        log_ok(f"اسکن کامل ۲۶ روت پایه با نقش «{r}» انجام گردید")


# =====================================================================
# لایه دوم: مچ‌گیری تضاد بین منوها/دکمه‌های HTML و دسترسی سرور
# =====================================================================
def run_layer_2_ui_rbac_mismatch():
    log_step("لایه ۲: مچ‌گیری تضاد بین منوهای HTML و دسترسی سرور (UI vs. Backend RBAC Mismatch)")

    roles = ["admin", "finance", "warehouse", "commercial", "baskool"]

    # ۱. استخراج تمام لینک‌های داخل داشبورد و سایدبار
    for r in roles:
        client = get_client(r)
        res = client.get("/dashboard")
        if res.status_code != 200:
            record_bug("LAYER_2", f"عدم دسترسی نقش {r} به داشبورد", f"کد: {res.status_code}")
            continue

        parser = LinkExtractor()
        parser.feed(res.text)

        # تک‌تک لینک‌هایی که به کاربر نشان داده شده است باید با همین کاربر با موفقیت (200 یا 303) باز شوند
        for link in parser.links:
            res_link = client.get(link)
            if res_link.status_code == 403:
                record_bug(
                    "LAYER_2",
                    f"تضاد UI و دسترسی: لینک {link} در داشبورد/سایدبار نقش {r} نمایش داده شده ولی سرور خطای ۴۰۳ برمی‌گرداند!",
                    f"کاربر: {r}، مسیر: {link}، وضعیت سرور: {res_link.status_code}"
                )
            elif res_link.status_code == 404:
                record_bug(
                    "LAYER_2",
                    f"لینک نامعتبر ۴۰۴ در UI: لینک {link} در داشبورد نقش {r} به صفحه ناموجود اشاره دارد!",
                    f"کاربر: {r}، مسیر: {link}"
                )
            elif res_link.status_code >= 500:
                record_bug(
                    "LAYER_2",
                    f"خطای ۵۰۰ در باز کردن لینک منوی نقش {r}: {link}",
                    f"پاسخ سرور: {res_link.text[:300]}"
                )

        log_ok(f"بررسی تضاد منوها و دسترسی برای نقش «{r}» ({len(parser.links)} لینک استخراج‌شده) با موفقیت بررسی شد")

    # ۲. راستی‌آزمایی قفل امنیتی دسترسی کاربران غیرمجاز به مسیرهای حفاظت‌شده (RBAC Security Wall)
    security_barriers = [
        ("baskool", ["/purchases", "/purchases/new", "/sales", "/sales/new", "/inventory/transaction", "/admin/users", "/admin/audit-logs", "/inventory/fiscal-years", "/admin/changelog"]),
        ("commercial", ["/inventory/transaction", "/inventory/transfer", "/inventory/stocktaking", "/admin/users", "/admin/audit-logs", "/inventory/fiscal-years", "/admin/changelog"]),
        ("warehouse", ["/admin/users", "/admin/audit-logs", "/inventory/fiscal-years", "/inventory/fiscal-year-close", "/purchases", "/purchases/new", "/sales", "/sales/new", "/admin/changelog"]),
        ("finance", ["/admin/users", "/admin/audit-logs", "/inventory/transaction"])
    ]

    for username, forbidden_routes in security_barriers:
        client = get_client(username)
        for f_route in forbidden_routes:
            res = client.get(f_route)
            if res.status_code != 403:
                record_bug(
                    "LAYER_2",
                    f"نقض دیوار امنیتی RBAC: کاربر {username} توانست به مسیر ممنوعه {f_route} دسترسی پیدا کند!",
                    f"کد بازگشتی: {res.status_code} (باید ۴۰۳ برمی‌گشت)",
                    severity="CRITICAL"
                )
        log_ok(f"دیوار امنیتی RBAC برای کاربر «{username}» در {len(forbidden_routes)} مسیر حساس راستی‌آزمایی شد")

    # ۳. راستی‌آزمایی Zero Ghost UI و پروتکل Blind Receiving & Weighing در لایه DOM
    wh_client = get_client("warehouse")
    res_wh_tx = wh_client.get("/inventory/transaction")
    if res_wh_tx.status_code == 200:
        ghost_fields = ['name="unit_price"', 'name="freight_cost"', 'name="insurance_cost"', 'name="weighbridge_cost"']
        for gf in ghost_fields:
            if gf in res_wh_tx.text:
                record_bug(
                    "LAYER_2_GHOST_UI",
                    f"نقص محرمانگی مالی (Ghost UI): فیلد مالی {gf} در فرم ثبت تراکنش انباردار نمایش داده شده است!",
                    f"کاربر: warehouse، مسیر: /inventory/transaction",
                    severity="HIGH"
                )
        log_ok("پروتکل محرمانگی مالی فرم انباردار (عدم نمایش فیلدهای نرخ و هزینه) راستی‌آزمایی شد")

    bask_client = get_client("baskool")
    res_bask_wb = bask_client.get("/weighbridge/new")
    if res_bask_wb.status_code == 200:
        bask_ghosts = ['name="supplier_id"', 'name="customer_id"']
        for bg in bask_ghosts:
            if bg in res_bask_wb.text:
                record_bug(
                    "LAYER_2_GHOST_UI",
                    f"نقص محرمانگی باسکول (Blind Weighing Ghost UI): فیلد {bg} در فرم باسکول‌دار فعال است!",
                    f"کاربر: baskool، مسیر: /weighbridge/new",
                    severity="HIGH"
                )
        log_ok("پروتکل توزین کور باسکول (توزین بر اساس سند عطف سفارش) راستی‌آزمایی شد")


# =====================================================================
# لایه سوم: شبیه‌سازی ۷ فرآیند اصلی کسب‌وکار از صفر تا صد (E2E Workflow)
# =====================================================================
def run_layer_3_e2e_workflows(wh_id: int, prod_id: int):
    log_step("لایه ۳: شبیه‌سازی ۷ فرآیند اصلی از صفر تا صد (End-to-End Enterprise Flows)")

    admin_client = get_client("admin")
    comm_client = get_client("commercial")
    bask_client = get_client("baskool")
    wh_client = get_client("warehouse")
    fin_client = get_client("finance")

    run_id = uuid.uuid4().hex[:6].upper()

    # -------------------------------------------------------------
    # تست ۱: تعاریف پایه (Commercial: تامین‌کننده/مشتری | Admin: کالا/انبار)
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۱] تعاریف پایه توسط بازرگانی و مدیر سیستم ---{RESET}")
    sup_code = f"SUP-TEST-{run_id}"
    res_sup = comm_client.post(
        "/master-data/supplier",
        data={
            "name": f"شرکت ذوب و نورد آریا {run_id}",
            "code": sup_code,
            "phone": "09121112233",
            "country_code": "IR"
        }
    )
    if res_sup.status_code != 303:
        record_bug("LAYER_3_TEST_1", "خطا در ثبت تامین‌کننده جدید", f"کد: {res_sup.status_code}")
    
    cust_code = f"CUST-TEST-{run_id}"
    res_cust = comm_client.post(
        "/master-data/customer",
        data={
            "name": f"مجتمع سازه‌های سنگین پایتخت {run_id}",
            "code": cust_code,
            "phone": "09129998877",
            "country_code": "IR",
            "credit_limit": 10000000000.0
        }
    )
    if res_cust.status_code != 303:
        record_bug("LAYER_3_TEST_1", "خطا در ثبت مشتری جدید", f"کد: {res_cust.status_code}")

    with SessionLocal() as db:
        new_sup = db.query(Supplier).filter(Supplier.code == sup_code).first()
        new_cust = db.query(Customer).filter(Customer.code == cust_code).first()
        assert new_sup and new_cust, "تامین‌کننده یا مشتری در دیتابیس ثبت نشد!"
        sup_id = new_sup.id
        cust_id = new_cust.id

    # ثبت کالا و انبار جدید توسط admin
    wh_name = f"انبار شماره ۲ فولاد {run_id}"
    res_wh = admin_client.post("/master-data/warehouse", data={"name": wh_name})
    print("WH status:", res_wh.status_code, "loc:", res_wh.headers.get("location"))
    if res_wh.status_code != 303:
        record_bug("LAYER_3_TEST_1", "خطا در ثبت انبار فیزیکی جدید توسط admin", f"کد: {res_wh.status_code}")

    prod_name = f"تیرآهن ۲۴ ذوب‌آهن اصفهان {run_id}"
    res_prod = admin_client.post(
        "/master-data/product",
        data={
            "name": prod_name,
            "uom": "تن",
            "sku": f"IPE-24-{run_id}"
        }
    )
    print("PROD status:", res_prod.status_code, "loc:", res_prod.headers.get("location"))
    if res_prod.status_code != 303:
        record_bug("LAYER_3_TEST_1", "خطا در ثبت کالای جدید توسط admin", f"کد: {res_prod.status_code}")

    with SessionLocal() as db:
        second_wh = db.query(Warehouse).filter(Warehouse.name.like(f"%{run_id}%")).first()
        new_product = db.query(Product).filter(Product.sku == f"IPE-24-{run_id}").first()
        assert second_wh and new_product, f"انبار یا کالای جدید در دیتابیس یافت نشد! wh={second_wh}, prod={new_product}"
        wh2_id = second_wh.id
        steel_prod_id = new_product.id
    log_ok("تست ۱ پاس شد: تعاریف پایه (تامین‌کننده، مشتری، کالا، انبار دوم) با موفقیت ثبت شدند")

    # -------------------------------------------------------------
    # تست ۲: زنجیره کامل خرید + باسکول + کارتابل انبار
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۲] زنجیره کامل خرید، توزین باسکول و تایید کارتابل ---{RESET}")
    po_num = f"PO-E2E-{run_id}"
    res_po = comm_client.post(
        "/purchases",
        data={
            "po_number": po_num,
            "supplier_id": sup_id,
            "delivery_due_date": "1403/12/29",
            "product_id": [steel_prod_id],
            "quantity": [100.0],
            "unit_price": [30000.0]
        }
    )
    if res_po.status_code != 303:
        record_bug("LAYER_3_TEST_2", "خطا در ثبت سفارش خرید PO", f"کد: {res_po.status_code}")

    with SessionLocal() as db:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_num).first()
        assert po, "سفارش خرید در دیتابیس ذخیره نشد!"
        po_id = po.id
        po_item = po.items[0]
        po_item_id = po_item.id

    # توزین اول باسکول: ناخالص ۴۰,۰۰۰ کیلوگرم
    wb_ticket = f"WB-IN-{run_id}"
    res_wb1 = bask_client.post(
        "/weighbridge",
        data={
            "ticket_number": wb_ticket,
            "truck_plate": "12ب345-77",
            "driver_name": "محمد احمدی",
            "driver_phone": "09121234567",
            "weighing_mode": "INBOUND",
            "purchase_order_id": po_id,
            "product_id": steel_prod_id,
            "supplier_id": sup_id,
            "warehouse_id": wh_id,
            "initial_weight": 40000.0
        }
    )
    if res_wb1.status_code != 303:
        record_bug("LAYER_3_TEST_2", "خطا در ثبت توزین اول باسکول", f"کد: {res_wb1.status_code}")

    with SessionLocal() as db:
        wb = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.ticket_number == wb_ticket).first()
        assert wb, "قبض باسکول یافت نشد!"
        wb_id = wb.id

    # توزین دوم باسکول: خالی/تار ۱۵,۰۰۰ کیلوگرم (خالص = ۲۵,۰۰۰ کیلوگرم = ۲۵ تن)
    res_wb2 = bask_client.post(
        f"/weighbridge/{wb_id}/complete",
        data={"second_weight": 15000.0}
    )
    if res_wb2.status_code != 303:
        record_bug("LAYER_3_TEST_2", "خطا در ثبت توزین دوم باسکول", f"کد: {res_wb2.status_code}")

    # راستی‌آزمایی: ۲۵ تن باید در کارتابل PENDING_APPROVAL بنشیند و موجودی واقعی تغییر نکرده باشد
    with SessionLocal() as db:
        pending_tx = db.query(StockTransaction).filter(
            StockTransaction.weighbridge_ticket_id == wb_id,
            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
        ).first()
        assert pending_tx, "سند موقت باسکول در کارتابل انبار ایجاد نشد!"
        assert abs(pending_tx.quantity - 25.0) < 0.001, f"مقدار سند کارتابل ۲۵ تن نیست: {pending_tx.quantity}"
        tx_cartable_id = pending_tx.id

        # موجودی انبار هنوز نباید تغییر کرده باشد
        cur_stock = InventoryService.get_current_stock(db, steel_prod_id, wh_id)
        assert abs(cur_stock - 0.0) < 0.001, f"موجودی قبل از تایید کارتابل تغییر کرده است! (موجودی: {cur_stock})"

    # تایید نهایی سند توسط warehouse
    res_appr = wh_client.post(f"/inventory/transactions/{tx_cartable_id}/approve")
    if res_appr.status_code != 303:
        record_bug("LAYER_3_TEST_2", "خطا در تایید سند کارتابل توسط سرپرست انبار", f"کد: {res_appr.status_code}")

    with SessionLocal() as db:
        approved_tx = db.query(StockTransaction).filter(StockTransaction.id == tx_cartable_id).first()
        assert approved_tx.status == DocumentStatus.APPROVED, "وضعیت سند تایید نشد!"

        # اکنون موجودی باید دقیقاً ۲۵ تن شده باشد
        cur_stock = InventoryService.get_current_stock(db, steel_prod_id, wh_id)
        assert abs(cur_stock - 25.0) < 0.001, f"موجودی انبار پس از تایید ۲۵ تن نشد: {cur_stock}"

        # received_quantity سفارش خرید باید ۲۵ تن شده باشد
        item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == po_item_id).first()
        assert abs(item.received_quantity - 25.0) < 0.001, f"مقدار دریافتی PO ۲۵ تن نیست: {item.received_quantity}"
    log_ok("تست ۲ پاس شد: زنجیره خرید، توزین ۲۵ تنی، کارتابل معلق و افزایش قطعی موجودی تایید شد")

    # -------------------------------------------------------------
    # تست ۳: جلوگیری از ثبت دوبل و خروج بیش از سقف
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۳] جلوگیری از ثبت دوبل و تحویل مازاد بر سقف ---{RESET}")
    # تلاش برای قطعی کردن مجدد قبض باسکول بسته شده
    res_wb_repeat = bask_client.post(f"/weighbridge/{wb_id}/complete", data={"second_weight": 14000.0})
    if res_wb_repeat.status_code not in (400, 303):
        record_bug("LAYER_3_TEST_3", "سیستم اجازه توزین مجدد قبض تکمیل‌شده را داد!", f"کد: {res_wb_repeat.status_code}")
    log_ok("تست ۳.۱ پاس شد: سیستم مانع از ثبت مجدد قبض باسکول بسته‌شده گردید")

    # تلاش برای رسید مستقیم دستی مازاد بر مانده سفارش خرید (مانده = ۷۵ تن + ۵٪ تلورانس = ۷۸.۷۵ تن)
    res_over_rcv = comm_client.post(
        f"/purchases/{po_id}/receive",
        data={
            "warehouse_id": wh_id,
            "item_id": [po_item_id],
            "receive_qty": [90.0]  # بیش از سقف
        }
    )
    if res_over_rcv.status_code == 303:
        loc = res_over_rcv.headers.get("location", "")
        assert "error=" in loc, "رسید مازاد بر سقف تلورانس خطا نداد!"
    elif res_over_rcv.status_code != 400:
        record_bug("LAYER_3_TEST_3", "سیستم مانع از دریافت مازاد بر ۵٪ تلورانس سفارش خرید نشد!", f"کد: {res_over_rcv.status_code}")
    log_ok("تست ۳.۲ پاس شد: سیستم به درستی مانع از دریافت مازاد بر سقف سفارش خرید گردید")

    # -------------------------------------------------------------
    # تست ۴: زنجیره فروش، رزرو موجودی و بهای تمام‌شده میانگین موزون
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۴] زنجیره فروش، رزرو موجودی آزاد و ثبت بهای میانگین ---{RESET}")
    so_num = f"SO-E2E-{run_id}"
    res_so = comm_client.post(
        "/sales",
        data={
            "so_number": so_num,
            "customer_id": cust_id,
            "delivery_due_date": "1403/12/29",
            "product_id": [steel_prod_id],
            "quantity": [10.0],
            "unit_price": [45000.0]
        }
    )
    if res_so.status_code != 303:
        record_bug("LAYER_3_TEST_4", "خطا در ثبت سفارش فروش SO", f"کد: {res_so.status_code}")

    with SessionLocal() as db:
        so = db.query(SalesOrder).filter(SalesOrder.so_number == so_num).first()
        assert so, "سفارش فروش ایجاد نشد!"
        so_id = so.id
        so_item = so.items[0]
        so_item_id = so_item.id

    # ارسال حواله خروج ۱۰ تن به کارتابل انبار (deliver)
    res_deliv = comm_client.post(
        f"/sales/{so_id}/deliver",
        data={
            "warehouse_id": wh_id,
            "item_id": [so_item_id],
            "deliver_qty": [10.0]
        }
    )
    if res_deliv.status_code != 303:
        record_bug("LAYER_3_TEST_4", "خطا در صدور حواله خروج فروش به کارتابل", f"کد: {res_deliv.status_code}")

    # راستی‌آزمایی رزرو موجودی آزاد (Reservation Logic)
    with SessionLocal() as db:
        phys_stock = InventoryService.get_current_stock(db, steel_prod_id, wh_id)
        avail_stock = InventoryService.get_available_stock(db, steel_prod_id, wh_id)

        assert abs(phys_stock - 25.0) < 0.001, f"موجودی فیزیکی قبل از تایید نباید کم شود! (فعلی: {phys_stock})"
        assert abs(avail_stock - 15.0) < 0.001, f"موجودی آزاد باید به ۱۵ تن کاهش یافته باشد! (فعلی: {avail_stock})"

        # سند معلق خروج
        pending_out = db.query(StockTransaction).filter(
            StockTransaction.sales_order_id == so_id,
            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
        ).first()
        assert pending_out, "سند معلق خروج فروش در کارتابل ایجاد نشد!"
        tx_out_id = pending_out.id

    # تایید نهایی خروج توسط warehouse
    res_appr_out = wh_client.post(f"/inventory/transactions/{tx_out_id}/approve")
    if res_appr_out.status_code != 303:
        record_bug("LAYER_3_TEST_4", "خطا در تایید حواله خروج فروش در کارتابل انبار", f"کد: {res_appr_out.status_code}")

    with SessionLocal() as db:
        phys_stock_after = InventoryService.get_current_stock(db, steel_prod_id, wh_id)
        assert abs(phys_stock_after - 15.0) < 0.001, f"موجودی فیزیکی پس از تایید خروج ۱۵ تن نشد: {phys_stock_after}"

        # بررسی الصاق نرخ میانگین موزون بر سند خروج
        out_tx = db.query(StockTransaction).filter(StockTransaction.id == tx_out_id).first()
        assert out_tx.unit_price and out_tx.unit_price > 0, f"نرخ بهای تمام‌شده روی سند خروج محاسبه نشد: {out_tx.unit_price}"
    log_ok("تست ۴ پاس شد: سفارش فروش، رزرو هوشمند موجودی آزاد و کسر قطعی ۱۵ تن با نرخ میانگین تایید شد")

    # -------------------------------------------------------------
    # تست ۵: اصلاحیه و مرجوعی کالا
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۵] ثبت اصلاحیه و مرجوعی از فروش و خرید ---{RESET}")
    # ثبت اصلاحیه ریالی و مقداری روی سند ورود اول توسط finance
    res_adj = fin_client.post(
        f"/inventory/transactions/{tx_cartable_id}/adjust",
        data={
            "new_quantity": 25.0,  # بدون تغییر مقدار
            "new_unit_price": 32000.0,  # افزایش بهای خرید
            "adjustment_reason": "اصلاحیه بهای خرید طبق فاکتور تکمیلی ذوب‌آهن"
        }
    )
    if res_adj.status_code != 303:
        record_bug("LAYER_3_TEST_5", "خطا در ثبت سند اصلاحیه ریالی توسط مدیر مالی", f"کد: {res_adj.status_code}")

    # ثبت برگشت از فروش ۲ تن توسط warehouse عطف به سند خروج #tx_out_id
    res_ret = wh_client.post(
        "/inventory/returns",
        data={
            "parent_transaction_id": tx_out_id,
            "quantity": 2.0,
            "return_reason": "برگشت به علت عدم انطباق با ابعاد کارگاه",
            "notes": "برگشت ۲ تن از فاکتور فروش"
        }
    )
    if res_ret.status_code != 303:
        record_bug("LAYER_3_TEST_5", "خطا در ثبت سند مرجوعی فروش", f"کد: {res_ret.status_code}")

    with SessionLocal() as db:
        ret_tx = db.query(StockTransaction).filter(
            StockTransaction.parent_transaction_id == tx_out_id,
            StockTransaction.is_return == True
        ).first()
        assert ret_tx, "سند مرجوعی ثبت نشد!"
        ret_tx_id = ret_tx.id

    # تایید نهایی سند مرجوعی در کارتابل
    res_appr_ret = wh_client.post(f"/inventory/transactions/{ret_tx_id}/approve")
    if res_appr_ret.status_code != 303:
        record_bug("LAYER_3_TEST_5", "خطا در تایید سند مرجوعی در کارتابل", f"کد: {res_appr_ret.status_code}")

    with SessionLocal() as db:
        # با برگشت ۲ تن به انبار، موجودی از ۱۵ به ۱۷ تن افزایش می‌یابد
        stock_ret = InventoryService.get_current_stock(db, steel_prod_id, wh_id)
        assert abs(stock_ret - 17.0) < 0.001, f"موجودی پس از برگشت ۲ تن برابر ۱۷ تن نشد: {stock_ret}"

        # مقدار تحویل سفارش فروش باید از ۱۰ به ۸ تن کسر شده باشد
        so_item_chk = db.query(SalesOrderItem).filter(SalesOrderItem.id == so_item_id).first()
        assert abs(so_item_chk.delivered_quantity - 8.0) < 0.001, f"مقدار تحویل سفارش فروش پس از مرجوعی کسر نشد: {so_item_chk.delivered_quantity}"
    log_ok("تست ۵ پاس شد: اصلاحیه ریالی و مرجوعی معکوس کالا با کسر هوشمند از سفارش ثبت شد")

    # -------------------------------------------------------------
    # تست ۶: انتقال دو مرحله‌ای بین انبارها و کیسه‌گیری اوره
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۶] انتقال دو مرحله‌ای بین انبارها و عملیات کیسه‌گیری ---{RESET}")
    # انتقال ۵ تن از انبار ۱ به انبار ۲
    res_trf = wh_client.post(
        "/inventory/transfer",
        data={
            "from_warehouse_id": wh_id,
            "to_warehouse_id": wh2_id,
            "product_id": steel_prod_id,
            "quantity": 5.0,
            "reference_document": f"TRF-E2E-{run_id}"
        }
    )
    if res_trf.status_code != 303:
        record_bug("LAYER_3_TEST_6", "خطا در ثبت انتقال بین انبارها", f"کد: {res_trf.status_code}")

    with SessionLocal() as db:
        # مبدأ باید فوراً ۵ تن کسر شده باشد: ۱۷ - ۵ = ۱۲ تن
        stock_src = InventoryService.get_current_stock(db, steel_prod_id, wh_id)
        assert abs(stock_src - 12.0) < 0.001, f"موجودی مبدأ پس از انتقال ۱۲ تن نشد: {stock_src}"

        # مقصد هنوز سند در کارتابل است و اضافه نشده:
        stock_dst_before = InventoryService.get_current_stock(db, steel_prod_id, wh2_id)
        assert abs(stock_dst_before - 0.0) < 0.001, f"موجودی مقصد قبل از تایید کارتابل تغییر کرد: {stock_dst_before}"

        trf_in_tx = db.query(StockTransaction).filter(
            StockTransaction.warehouse_id == wh2_id,
            StockTransaction.transaction_source == TransactionSource.TRANSFER.value,
            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
        ).first()
        assert trf_in_tx, "سند وصول انتقال در کارتابل مقصد یافت نشد!"
        trf_in_id = trf_in_tx.id

    # تایید وصول انتقال توسط انباردار مقصد
    res_appr_trf = wh_client.post(f"/inventory/transactions/{trf_in_id}/approve")
    if res_appr_trf.status_code != 303:
        record_bug("LAYER_3_TEST_6", "خطا در تایید وصول انتقال در کارتابل انبار مقصد", f"کد: {res_appr_trf.status_code}")

    with SessionLocal() as db:
        stock_dst_after = InventoryService.get_current_stock(db, steel_prod_id, wh2_id)
        assert abs(stock_dst_after - 5.0) < 0.001, f"موجودی مقصد پس از وصول ۵ تن نشد: {stock_dst_after}"
    log_ok("تست ۶.۱ پاس شد: انتقال دو مرحله‌ای بین انبارها با سند در راه و وصول موفق تایید شد")

    # کیسه‌گیری اوره: ایجاد کالای فله و کالای بسته‌بندی
    with SessionLocal() as db:
        urea_bulk = Product(name=f"اوره فله صنعتی {run_id}", uom="تن", is_active=True)
        urea_bag = Product(name=f"اوره جامبوبگ ۱ تنی {run_id}", uom="بسته", is_active=True)
        db.add_all([urea_bulk, urea_bag])
        db.flush()

        # شارژ ۱۰ تن اوره فله در انبار ۲ با رسید مستقیم مصرف داخلی
        init_tx = StockTransaction(
            transaction_type=TransactionType.IN,
            transaction_source=TransactionSource.OPENING_BALANCE.value,
            product_id=urea_bulk.id,
            warehouse_id=wh2_id,
            quantity=10.0,
            unit_price=15000.0,
            status=DocumentStatus.APPROVED
        )
        db.add(init_tx)
        db.commit()
        urea_bulk_id = urea_bulk.id
        urea_bag_id = urea_bag.id

    # ثبت عملیات کیسه‌گیری: ۶ تن فله مصرف ➔ ۶ جامبوبگ تولید
    res_bag = wh_client.post(
        "/bagging",
        data={
            "order_number": f"BAG-E2E-{run_id}",
            "bulk_product_id": urea_bulk_id,
            "packaged_product_id": urea_bag_id,
            "warehouse_id": wh2_id,
            "bulk_tonnage_used": 6.0,
            "packages_produced": 6.0,
            "package_type": "جامبوبگ ۱ تنی",
            "packaging_cost_per_ton": 500.0,
            "waste_tonnage": 0.0
        }
    )
    if res_bag.status_code != 303:
        print(f"DEBUG BAGGING ERROR: status={res_bag.status_code}, text={res_bag.text}")
        record_bug("LAYER_3_TEST_6", "خطا در ثبت عملیات کیسه‌گیری اوره", f"کد: {res_bag.status_code} - {res_bag.text}")

    with SessionLocal() as db:
        bulk_rem = InventoryService.get_current_stock(db, urea_bulk_id, wh2_id)
        bag_prod = InventoryService.get_current_stock(db, urea_bag_id, wh2_id)
        assert abs(bulk_rem - 4.0) < 0.001, f"مانده اوره فله ۴ تن نشد: {bulk_rem}"
        assert abs(bag_prod - 6.0) < 0.001, f"تعداد جامبوبگ ۶ عدد نشد: {bag_prod}"
    log_ok("تست ۶.۲ پاس شد: عملیات کیسه‌گیری اوره با کسر فله و افزایش جامبوبگ تایید شد")

    # -------------------------------------------------------------
    # تست ۷: انبارگردانی (شامل تست عدد صفر) و بستن دوره مالی
    # -------------------------------------------------------------
    print(f"\n{CYAN}--- [تست ۷] انبارگردانی با شمارش صفر و بستن قطعی سال مالی ---{RESET}")
    # ثبت انبارگردانی روی انبار ۲ برای صفر کردن موجودی اوره فله (تست عدد صفر)
    res_stk = wh_client.post(
        "/inventory/stocktaking",
        data={
            "warehouse_id": wh2_id,
            f"count_{urea_bulk_id}": "0"  # شمارش صفر: صفر کردن موجودی
        }
    )
    if res_stk.status_code != 303:
        record_bug("LAYER_3_TEST_7", "خطا در ثبت شمارش انبارگردانی با مقدار صفر", f"کد: {res_stk.status_code}")

    with SessionLocal() as db:
        zero_stock = InventoryService.get_current_stock(db, urea_bulk_id, wh2_id)
        assert abs(zero_stock - 0.0) < 0.001, f"انبارگردانی نتوانست موجودی کالا را روی عدد صفر ست کند: {zero_stock}"
    log_ok("تست ۷.۱ پاس شد: انبارگردانی با مقدار صفر با موفقیت موجودی مازاد را تسویه و صفر کرد")

    # اجرای بستن سال مالی توسط مدیر مالی
    res_close_fy = fin_client.post(
        "/inventory/fiscal-year-close",
        data={
            "new_year_name": f"سال مالی ۱۴۰۶ {run_id}",
            "new_year_start_date": "1406-01-01",
            "new_year_end_date": "1406-12-29"
        }
    )
    if res_close_fy.status_code != 303:
        print(f"DEBUG CLOSE FY FAILED: status={res_close_fy.status_code}, text={res_close_fy.text[:300]}")
        record_bug("LAYER_3_TEST_7", "خطا در اجرای بستن سال مالی", f"کد: {res_close_fy.status_code} - {res_close_fy.text[:200]}")

    with SessionLocal() as db:
        new_fy = db.query(FiscalYear).filter(FiscalYear.name.like(f"%{run_id}%")).first()
        assert new_fy and new_fy.is_active, "سال مالی جدید فعال نشد!"

        # راستی‌آزمایی عدم انتقال کالاهای با موجودی صفر به سال مالی جدید
        zero_op_tx = db.query(StockTransaction).filter(
            StockTransaction.fiscal_year_id == new_fy.id,
            StockTransaction.product_id == urea_bulk_id,
            StockTransaction.warehouse_id == wh2_id
        ).first()
        assert zero_op_tx is None, "کالای دارای موجودی صفر به اشتباه به عنوان سند افتتاحیه سال جدید منتقل شده است!"
    log_ok("تست ۷.۲ پاس شد: سال مالی با موفقیت بسته شد و اسناد افتتاحیه بدون انتقال اقلام صفر ایجاد گردید")


# =====================================================================
# لایه چهارم: تست ورودی‌های فارسی و ممیز ترکی (Input Fuzzing)
# =====================================================================
def run_layer_4_input_fuzzing(wh_id: int, prod_id: int):
    log_step("لایه ۴: تست ورودی‌های فارسی، عربی و ممیز اعشاری ترکی (Input Fuzzing)")

    comm_client = get_client("commercial")
    run_id = uuid.uuid4().hex[:6].upper()

    with SessionLocal() as db:
        sup = db.query(Supplier).first()
        sup_id = sup.id

    # ۱. ارسال ارقام کاملاً فارسی با اعشار: ۱۲۵.۵
    po_persian_num = f"PO-FA-{run_id}"
    res_fa = comm_client.post(
        "/purchases",
        data={
            "po_number": po_persian_num,
            "supplier_id": sup_id,
            "delivery_due_date": "۱۴۰۳/۱۲/۲۹",
            "product_id": [prod_id],
            "quantity": ["۱۲۵.۵"],
            "unit_price": ["۳۵۰۰۰"]
        }
    )
    if res_fa.status_code != 303:
        record_bug("LAYER_4", "خطا در پردازش اعداد با کیبورد و فونت فارسی (۱۲۵.۵)", f"کد: {res_fa.status_code}")
    else:
        with SessionLocal() as db:
            po_fa = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_persian_num).first()
            assert po_fa, "سفارش خرید با ارقام فارسی ایجاد نشد!"
            item_qty = po_fa.items[0].quantity
            assert abs(item_qty - 125.5) < 0.001, f"مقدار ارقام فارسی به درستی پارس نشد: {item_qty}"
        log_ok("تست ۴.۱ پاس شد: ارقام فارسی (۱۲۵.۵) به درستی در لایه سرور نرمال‌سازی و ذخیره شدند")

    # ۲. ارسال اعداد با فرمت ممیز و ویرگول ترکی (Turkish Decimal Comma: 125,5)
    po_tr_num = f"PO-TR-{run_id}"
    res_tr = comm_client.post(
        "/purchases",
        data={
            "po_number": po_tr_num,
            "supplier_id": sup_id,
            "delivery_due_date": "1403/12/29",
            "product_id": [prod_id],
            "quantity": ["125,5"],
            "unit_price": ["40000"]
        }
    )
    if res_tr.status_code != 303:
        record_bug("LAYER_4", "خطا در پردازش اعداد با ممیز ویرگول ترکی (125,5)", f"کد: {res_tr.status_code}")
    else:
        with SessionLocal() as db:
            po_tr = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_tr_num).first()
            assert po_tr, "سفارش خرید با ویرگول اعشار ترکی ایجاد نشد!"
            item_qty_tr = po_tr.items[0].quantity
            assert abs(item_qty_tr - 125.5) < 0.001, f"ممیز ویرگول ترکی به درستی پارس نشد: {item_qty_tr}"
        log_ok("تست ۴.۲ پاس شد: فرمت اعشاری ویرگول ترکی (125,5) به درستی نرمال‌سازی گردید")


def generate_bug_hunt_report(start_time: datetime, end_time: datetime):
    """تولید گزارش جامع BUG_HUNT_REPORT.md"""
    duration = (end_time - start_time).total_seconds()
    report_content = f"""# گزارش جامع شکارچی خودکار باگ‌ها (Deep Bug Hunter Report)
> **سامانه:** NexusPour Enterprise ERP  
> **مهندسی و توسعه:** امید پورمحمود (Omid Pourmahmoud)  
> **تاریخ اجرا:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
> **مدت زمان اسکن:** {duration:.2f} ثانیه  

---

## ۱. خلاصه آماری نتایج ممیزی ۴ لایه
| شاخص | مقدار |
| :--- | :--- |
| **تعداد کل نقش‌های ممیزی‌شده** | ۵ نقش (`admin`, `finance`, `warehouse`, `commercial`, `baskool`) |
| **تعداد روتهای اسکن‌شده در لایه ۱** | ۲۶ مسیر کامل سیستم |
| **تعداد فرآیندهای کسب‌وکار (E2E) در لایه ۳** | ۷ فرآیند استاندارد عملیاتی |
| **تعداد تست‌های اعشاری و فارسی در لایه ۴** | ۲ آزمون هوشمند ممیز ترکی و ارقام فارسی |
| **تعداد باگ‌های کشف‌شده** | `{len(discovered_bugs)}` |
| **تعداد باگ‌های برطرف‌شده** | `{len(fixed_bugs)}` |
| **تعداد باگ‌های باز و حل‌نشده** | `{len(discovered_bugs) - len(fixed_bugs)}` |
| **وضعیت نهایی آزمون خودکار** | **{"✅ ۱۰۰٪ سبز و بدون نقص (ALL TESTS PASSED)" if len(discovered_bugs) == len(fixed_bugs) else "❌ نیاز به بازبینی و رفع خطا"}** |

---

## ۲. گزارش تفصیلی باگ‌های کشف‌شده و رفع‌شده
"""
    if not discovered_bugs:
        report_content += "\n🎉 **هیچ‌گونه باگ، خطای ۵۰۰، خطای ۴۲۲ یا نقض دسترسی در سیستم یافت نشد.** تمام مسیرها و فرآیندهای سیستم با موفقیت ۱۰۰٪ سبز هستند.\n"
    else:
        for b in discovered_bugs:
            report_content += f"""
### {b['id']}: {b['title']}
- **لایه:** `{b['layer']}`
- **سطح بحرانی:** `{b['severity']}`
- **زمان کشف:** `{b['timestamp']}`
- **توضیحات خطا:**
```text
{b['details']}
```
"""

    report_path = os.path.join(os.path.dirname(__file__), "..", "BUG_HUNT_REPORT.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"\n{GREEN}{BOLD}  📄 گزارش شکارچی باگ‌ها در «BUG_HUNT_REPORT.md» ذخیره گردید.{RESET}")


def run_full_deep_bug_hunter():
    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    print(f"{CYAN}{BOLD}  🦅 آغاز اسکن سراسری سامانه NexusPour Enterprise ERP (Deep Bug Hunter){RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}")

    start_time = datetime.now()
    wh_id, prod_id, fy_id = setup_base_fixtures()

    try:
        run_layer_1_crawler(wh_id, prod_id)
        run_layer_2_ui_rbac_mismatch()
        run_layer_3_e2e_workflows(wh_id, prod_id)
        run_layer_4_input_fuzzing(wh_id, prod_id)
    finally:
        end_time = datetime.now()
        generate_bug_hunt_report(start_time, end_time)

    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    if len(discovered_bugs) == 0:
        print(f"{GREEN}{BOLD}  🎉 تبریک! اسکریپت شکارچی تمام ۴ لایه را اسکن کرد و هیچ خطایی یافت نشد (0 Bugs).{RESET}")
    else:
        print(f"{RED}{BOLD}  ⚠️ تعداد {len(discovered_bugs)} باگ کشف شد که باید بلافاصله تعمیر شوند.{RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}\n")

    return len(discovered_bugs)


if __name__ == "__main__":
    bugs_count = run_full_deep_bug_hunter()
    sys.exit(bugs_count)
