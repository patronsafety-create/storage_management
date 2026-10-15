"""
بازرس خودکار چرخه کار و امنیت دسترسی سازمانی (Workflow Inspector & Automated End-to-End Auditor)
طراحی و مهندسی: امید پورمحمود (Omid Pourmahmoud)
NexusPour Enterprise ERP
"""
import sys
import os
import uuid

# تنظیم مسیر روت پروژه
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient

from src.api.main import app
from src.infrastructure.database import SessionLocal
from src.infrastructure.seed_users import seed_enterprise_users
from src.domain_model.auth_models import User, Role
from src.domain_model.inventory_models import (
    Product, Warehouse, Supplier, Customer, PurchaseOrder, PurchaseOrderItem,
    SalesOrder, SalesOrderItem, StockTransaction, WeighbridgeTicket, FiscalYear,
    TransactionType
)
from src.domain_model.enums import (
    DocumentStatus, PurchaseOrderStatus, SalesOrderStatus, WeighbridgeStatus
)
from src.services.inventory_service import InventoryService


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def log_step(msg: str):
    print(f"\n{BLUE}{BOLD}=== [TEST STEP] {msg} ==={RESET}")

def log_success(msg: str):
    print(f"{GREEN}  ✔ {msg}{RESET}")

def log_fail(msg: str):
    print(f"{RED}  ✖ [FAILED] {msg}{RESET}")


def get_auth_client(username: str, password: str = "1234") -> TestClient:
    """ایجاد کلاینت تست احرازشده به ازای هر کاربر سازمانی"""
    client = TestClient(app, follow_redirects=False)
    res = client.post("/login", data={"username": username, "password": password})
    assert res.status_code == 303, f"لاگین کاربر {username} ناموفق بود! کد وضعیت: {res.status_code}"
    assert "access_token" in client.cookies, f"کوکی access_token برای {username} صادر نشد!"
    return client


def setup_initial_database_fixtures():
    """آماده‌سازی سال مالی، انبار و کالای آزمایشی در صورت خالی بودن دیتابیس"""
    with SessionLocal() as db:
        seed_enterprise_users(db)

        # سال مالی فعال
        fy = db.query(FiscalYear).filter(FiscalYear.is_active == True, FiscalYear.is_closed == False).first()
        if not fy:
            fy = FiscalYear(name="سال مالی ۱۴۰۵", start_date="1405/01/01", end_date="1405/12/29", is_active=True, is_closed=False)
            db.add(fy)
            db.flush()

        # انبار تستی
        wh = db.query(Warehouse).first()
        if not wh:
            wh = Warehouse(name="انبار مرکزی تهران", location="تهران - کیلومتر ۱۵ جاده مخصوص", currency="IRR")
            db.add(wh)
            db.flush()

        # کالای تستی (میلگرد استاندارد)
        prod = db.query(Product).first()
        if not prod:
            prod = Product(
                name="میلگرد ۱۶ آجدار A3 فولاد خراسان",
                uom="کیلوگرم",
                secondary_uom="شاخه",
                nominal_weight=18.96,
                sku="REB-16-A3-KHORASAN",
                is_active=True
            )
            db.add(prod)
            db.flush()

        db.commit()
        return wh.id, prod.id, fy.id


def test_1_user_logins():
    """۱. لاگین با هر ۵ کاربر با رمز ۱۲۳۴"""
    log_step("۱. احراز هویت و لاگین هر ۵ نقش سازمانی (Admin, Finance, Warehouse, Commercial, Baskool)")
    users = ["admin", "finance", "warehouse", "commercial", "baskool"]

    for u in users:
        client = get_auth_client(u, "1234")
        dash_res = client.get("/dashboard")
        assert dash_res.status_code == 200, f"داشبورد برای {u} باز نشد (کد {dash_res.status_code})"
        log_success(f"ورود موفق کاربر «{u}» با رمز ۱۲۳۴ و بارگذاری بی‌نقص داشبورد")


def test_2_rbac_security_barriers():
    """۲. بررسی اینکه baskool و commercial به /inventory/transaction و /admin/audit-logs دسترسی ندارند (403)"""
    log_step("۲. راستی‌آزمایی قفل امنیتی دسترسی (RBAC Barrier) برای اپراتور باسکول و کارشناس بازرگانی")
    
    baskool_client = get_auth_client("baskool", "1234")
    commercial_client = get_auth_client("commercial", "1234")

    # تست baskool
    res_b_inv = baskool_client.get("/inventory/transaction")
    assert res_b_inv.status_code == 403, f"انتظار خطای ۴۰۳ برای baskool در /inventory/transaction بود اما کد {res_b_inv.status_code} بازگشت!"
    log_success("مسیر /inventory/transaction برای اپراتور باسکول مسدود است (403 Forbidden)")

    res_b_audit = baskool_client.get("/admin/audit-logs")
    assert res_b_audit.status_code == 403, f"انتظار خطای ۴۰۳ برای baskool در /admin/audit-logs بود اما کد {res_b_audit.status_code} بازگشت!"
    log_success("مسیر /admin/audit-logs برای اپراتور باسکول مسدود است (403 Forbidden)")

    # تست commercial
    res_c_inv = commercial_client.get("/inventory/transaction")
    assert res_c_inv.status_code == 403, f"انتظار خطای ۴۰۳ برای commercial در /inventory/transaction بود اما کد {res_c_inv.status_code} بازگشت!"
    log_success("مسیر /inventory/transaction برای کارشناس بازرگانی مسدود است (403 Forbidden)")

    res_c_audit = commercial_client.get("/admin/audit-logs")
    assert res_c_audit.status_code == 403, f"انتظار خطای ۴۰۳ برای commercial در /admin/audit-logs بود اما کد {res_c_audit.status_code} بازگشت!"
    log_success("مسیر /admin/audit-logs برای کارشناس بازرگانی مسدود است (403 Forbidden)")


def test_3_commercial_actions(wh_id: int, prod_id: int):
    """۳. بررسی اینکه commercial می‌تواند تامین‌کننده، مشتری، سفارش خرید (PO) و سفارش فروش (SO) ثبت کند"""
    log_step("۳. راستی‌آزمایی اختیارات بازرگانی: ثبت تامین‌کننده، مشتری، سفارش خرید PO و فروش SO")
    commercial_client = get_auth_client("commercial", "1234")
    run_id = uuid.uuid4().hex[:6].upper()

    # ۱. ثبت تامین‌کننده
    sup_code = f"SUP-TEST-{run_id}"
    sup_name = f"شرکت ذوب‌آهن تستی بازرگانی {run_id}"
    res_sup = commercial_client.post(
        "/master-data/supplier",
        data={
            "name": sup_name,
            "code": sup_code,
            "contact_person": "مهندس صادقی",
            "phone": "09121112233",
            "country_code": "IR"
        }
    )
    assert res_sup.status_code == 303, f"خطا در ثبت تامین‌کننده: {res_sup.status_code} {res_sup.text}"
    loc = res_sup.headers.get("location", "")
    assert "error=" not in loc, f"ثبت تامین‌کننده با خطا ریدایرکت شد: {loc}"
    
    with SessionLocal() as db:
        supplier = db.query(Supplier).filter(Supplier.code == sup_code).first()
        assert supplier is not None, f"تامین‌کننده در دیتابیس ذخیره نشد! location: {loc}"
        supplier_id = supplier.id
        log_success(f"تامین‌کننده «{sup_name}» با موفقیت توسط commercial ثبت شد (ID: {supplier.id})")

    # ۲. ثبت مشتری
    cust_code = f"CUST-TEST-{run_id}"
    cust_name = f"مجتمع فولاد گستر پارس تستی {run_id}"
    res_cust = commercial_client.post(
        "/master-data/customer",
        data={
            "name": cust_name,
            "code": cust_code,
            "contact_person": "دکتر حسینی",
            "phone": "09124445566",
            "country_code": "IR",
            "credit_limit": 5000000000.0
        }
    )
    assert res_cust.status_code == 303, f"خطا در ثبت مشتری: {res_cust.status_code} {res_cust.text}"
    loc_c = res_cust.headers.get("location", "")
    assert "error=" not in loc_c, f"ثبت مشتری با خطا ریدایرکت شد: {loc_c}"
    
    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.code == cust_code).first()
        assert customer is not None, "مشتری در دیتابیس ذخیره نشد!"
        customer_id = customer.id
        log_success(f"مشتری «{cust_name}» با موفقیت توسط commercial ثبت شد (ID: {customer.id})")

    # ۳. ثبت سفارش خرید (PO)
    po_num = f"PO-COMM-{run_id}"
    res_po = commercial_client.post(
        "/purchases",
        data={
            "po_number": po_num,
            "supplier_id": supplier_id,
            "delivery_due_date": "1403/12/29",
            "notes": "سفارش خرید آزمایشی بازرس خودکار",
            "product_id": [prod_id],
            "quantity": [5000.0],
            "unit_price": [28000.0]
        }
    )
    assert res_po.status_code == 303, f"خطا در ثبت سفارش خرید PO: {res_po.status_code} {res_po.text}"
    with SessionLocal() as db:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_num).first()
        assert po is not None, "سفارش خرید در دیتابیس ایجاد نشد!"
        po_id = po.id
        log_success(f"سفارش خرید «{po_num}» با موفقیت ثبت گردید (مبلغ: {po.total_amount:,.0f} ریال)")

    # راستی‌آزمایی بارگذاری صفحه مشاهده جزئیات سفارش خرید (جلوگیری از خطای ۵۰۰)
    res_po_view = commercial_client.get(f"/purchases/{po_id}")
    assert res_po_view.status_code == 200, f"صفحه جزئیات سفارش خرید با خطای {res_po_view.status_code} مواجه شد!"
    log_success(f"صفحه جزئیات سفارش خرید #{po_id} با موفقیت بارگذاری شد (200 OK)")

    # ۴. ثبت سفارش فروش (SO)
    so_num = f"SO-COMM-{run_id}"
    res_so = commercial_client.post(
        "/sales",
        data={
            "so_number": so_num,
            "customer_id": customer_id,
            "delivery_due_date": "1403/12/29",
            "notes": "سفارش فروش آزمایشی بازرس خودکار",
            "product_id": [prod_id],
            "quantity": [2000.0],
            "unit_price": [35000.0]
        }
    )
    assert res_so.status_code == 303, f"خطا در ثبت سفارش فروش SO: {res_so.status_code} {res_so.text}"
    with SessionLocal() as db:
        so = db.query(SalesOrder).filter(SalesOrder.so_number == so_num).first()
        assert so is not None, "سفارش فروش در دیتابیس ایجاد نشد!"
        so_id = so.id
        log_success(f"سفارش فروش «{so_num}» با موفقیت ثبت گردید (مبلغ: {so.total_amount:,.0f} ریال)")

    # راستی‌آزمایی بارگذاری صفحه مشاهده جزئیات سفارش فروش (رفع باگ ۵۰۰ در قالب sales_detail.html)
    res_so_view = commercial_client.get(f"/sales/{so_id}")
    assert res_so_view.status_code == 200, f"صفحه جزئیات سفارش فروش با خطای {res_so_view.status_code} مواجه شد!"
    log_success(f"صفحه جزئیات سفارش فروش #{so_id} با موفقیت بارگذاری شد (200 OK - بدون خطای tax_info)")

    # ۵. راستی‌آزمایی مهار هوشمند خروج مازاد بر موجودی بدون خطای خام ۴۰۰
    with SessionLocal() as db:
        item = db.query(SalesOrderItem).filter(SalesOrderItem.sales_order_id == so_id).first()
        item_id = item.id

    res_deliver_fail = commercial_client.post(
        f"/sales/{so_id}/deliver",
        data={
            "warehouse_id": wh_id,
            "item_id": [item_id],
            "deliver_qty": [9999999.0]
        }
    )
    assert res_deliver_fail.status_code == 303, f"کد غیرمنتظره {res_deliver_fail.status_code} حین خروج مازاد بر موجودی!"
    loc = res_deliver_fail.headers.get("location", "")
    assert "error=" in loc, f"خطای عدم موجودی در ریدایرکت ثبت نشد: {loc}"
    log_success("سیستم با موفقیت درخواست خروج مازاد بر موجودی را مهار کرد (هدایت امن با بنر خطا بدون خطای خام ۴۰۰)")

    # ۶. استعلام زنده موجودی آزاد از API
    res_stock = commercial_client.get(f"/api/stock/{prod_id}/{wh_id}")
    assert res_stock.status_code == 200, f"خطا در استعلام API موجودی: {res_stock.status_code}"
    stock_json = res_stock.json()
    assert "available_stock" in stock_json, "فیلد available_stock در خروجی API یافت نشد!"
    log_success(f"استعلام زنده موجودی از API با موفقیت انجام شد (موجودی آزاد: {stock_json['available_stock']})")

    return supplier_id, customer_id


def test_4_full_lifecycle_workflow(wh_id: int, prod_id: int, supplier_id: int):
    """
    ۴. اجرای چرخه کامل عملیاتی ERP:
    ثبت PO توسط commercial ➔ توزین اول و دوم توسط baskool ➔ تایید در کارتابل توسط warehouse ➔ بررسی افزایش موجودی انبار و بسته شدن PO
    """
    log_step("۴. اجرای چرخه کامل عملیاتی (End-to-End Enterprise Flow): بازرگانی ➔ باسکول ➔ کارتابل انبار")
    
    commercial_client = get_auth_client("commercial", "1234")
    baskool_client = get_auth_client("baskool", "1234")
    warehouse_client = get_auth_client("warehouse", "1234")
    run_id = uuid.uuid4().hex[:6].upper()

    # موجودی اولیه کالا در انبار هدف
    with SessionLocal() as db:
        wh = db.query(Warehouse).filter_by(id=wh_id).first()
        prod = db.query(Product).filter_by(id=prod_id).first()
        stock_initial = InventoryService.get_current_stock(db, prod.id, wh.id)
        log_success(f"موجودی اولیه کالای «{prod.name}» در «{wh.name}»: {stock_initial:,.3f} {prod.uom}")

    # تعیین مقدار متناسب با واحد کالا (تن یا کیلوگرم)
    with SessionLocal() as db:
        prod = db.query(Product).filter_by(id=prod_id).first()
        is_ton = prod.uom in ("تن", "ton", "Ton")
        po_qty = 10.0 if is_ton else 10000.0
        expected_qty = 10.0 if is_ton else 10000.0

    # گام ۱: بازرگانی سفارش خرید ثبت می‌کند
    po_num = f"PO-FLOW-{run_id}"
    res_po = commercial_client.post(
        "/purchases",
        data={
            "po_number": po_num,
            "supplier_id": supplier_id,
            "delivery_due_date": "1403/12/29",
            "notes": "سفارش خرید جریان کامل تستی",
            "product_id": [prod_id],
            "quantity": [po_qty],
            "unit_price": [30000.0]
        }
    )
    assert res_po.status_code == 303
    with SessionLocal() as db:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == po_num).first()
        assert po is not None
        assert po.status == PurchaseOrderStatus.CONFIRMED
        po_id = po.id
        po_item_id = po.items[0].id
        log_success(f"گام ۱ (بازرگانی): سفارش خرید {po_num} به مقدار {po_qty:,.0f} در وضعیت CONFIRMED ایجاد شد")

    # گام ۲: کامیون حامل بار وارد باسکول می‌شود ➔ باسکول توزین اول را ثبت می‌کند
    ticket_num = f"WB-{run_id}"
    gross_wt = 36000.0
    res_wb1 = baskool_client.post(
        "/weighbridge",
        data={
            "ticket_number": ticket_num,
            "truck_plate": f"۶۸ع{run_id[:3]}ایران۱۱",
            "driver_name": "احمد اکبری",
            "driver_phone": "09127778899",
            "truck_type": "تریلی کفی ۱۸ چرخ",
            "weighing_mode": "INBOUND",
            "initial_weight": gross_wt,
            "max_allowed_weight": 40000.0,
            "product_id": prod_id,
            "warehouse_id": wh_id,
            "supplier_id": supplier_id,
            "purchase_order_id": po_id,
            "notes": "ورود پر جهت تخلیه میلگرد سفارش خرید"
        }
    )
    assert res_wb1.status_code == 303
    with SessionLocal() as db:
        ticket = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.ticket_number == ticket_num).first()
        assert ticket is not None
        assert ticket.status == WeighbridgeStatus.FIRST_WEIGHING
        ticket_id = ticket.id
        log_success(f"گام ۲ (باسکول): توزین اول قبض {ticket_num} ثبت شد (وزن ناخالص: {gross_wt:,.0f} کیلوگرم، وضعیت: FIRST_WEIGHING)")

    # گام ۳ (تست باگ ۴): جلوگیری از ثبت مضاعف دستی هنگامی که قبض باسکول باز است
    res_duplicate_attempt = commercial_client.post(
        f"/purchases/{po_id}/receive",
        data={
            "warehouse_id": wh_id,
            "item_id": [po_item_id],
            "receive_qty": [po_qty]
        }
    )
    assert res_duplicate_attempt.status_code in (400, 303), "سیستم باید جلوی ثبت دستی را در زمان حضور کامیون روی باسکول بگیرد!"
    if res_duplicate_attempt.status_code == 303:
        assert "error=" in res_duplicate_attempt.headers.get("location", ""), "پیام خطا در ریدایرکت ثبت نشد!"
    log_success("گام ۳ (کنترل باگ ۴): سیستم با موفقیت از ثبت مضاعف دستی حین توزین اول جلوگیری کرد (مهار با ریدایرکت/پیام خطا)")

    # گام ۴: کامیون پس از تخلیه بار به باسکول بازمی‌گردد ➔ توزین دوم (تار/خالی) ثبت می‌شود
    tare_wt = 26000.0  # وزن خالص = 10,000 کیلوگرم دقیقاً برابر با سفارش
    res_wb2 = baskool_client.post(
        f"/weighbridge/{ticket_id}/complete",
        data={
            "second_weight": tare_wt,
            "auto_create_transaction": True
        }
    )
    assert res_wb2.status_code == 303
    with SessionLocal() as db:
        ticket = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.id == ticket_id).first()
        assert ticket.status == WeighbridgeStatus.COMPLETED
        assert ticket.net_weight == 10000.0
        assert ticket.stock_transaction_id is not None
        tx_id = ticket.stock_transaction_id
        log_success(f"گام ۴ (باسکول): توزین دوم قبض {ticket_num} قطعی شد (وزن خالص: {ticket.net_weight:,.0f} کیلوگرم ➔ سند کارتابل صادر گردید)")

    # گام ۵: بررسی سند در کارتابل تایید سرپرست انبار
    with SessionLocal() as db:
        tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
        assert tx is not None
        assert tx.status == DocumentStatus.PENDING_APPROVAL
        assert tx.quantity == expected_qty
        log_success(f"گام ۵ (کارتابل): سند رسید موقت #{tx.id} به مقدار {tx.quantity:,.3f} در وضعیت PENDING_APPROVAL رویت شد")

    # گام ۶: سرپرست انبار سند را تایید نهایی می‌کند
    res_approve = warehouse_client.post(f"/inventory/transactions/{tx_id}/approve")
    assert res_approve.status_code == 303
    log_success(f"گام ۶ (انباردار): سند #{tx_id} توسط سرپرست انبار تایید قطعی شد (DocumentStatus.APPROVED)")

    # گام ۷: راستی‌آزمایی موجودی قطعی انبار و بسته شدن سفارش خرید
    with SessionLocal() as db:
        tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == po_id).first()
        po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == po_item_id).first()
        prod = db.query(Product).filter_by(id=prod_id).first()

        assert tx.status == DocumentStatus.APPROVED
        stock_final = InventoryService.get_current_stock(db, prod_id, wh_id)
        expected_stock = stock_initial + po_qty
        assert abs(stock_final - expected_stock) < 0.001, f"موجودی انبار افزایش نیافت! فعلی: {stock_final}، مورد انتظار: {expected_stock}"
        log_success(f"گام ۷.۱ (موجودی انبار): موجودی انبار از {stock_initial:,.3f} به {stock_final:,.3f} {prod.uom} با موفقیت افزایش یافت (+{po_qty:,.0f})")

        assert po_item.received_quantity == po_qty, f"مقدار دریافتی سفارش ({po_item.received_quantity}) با مقدار سفارش تطابق ندارد!"
        assert po.status == PurchaseOrderStatus.COMPLETED, f"وضعیت سفارش خرید باید COMPLETED باشد اما {po.status} است!"
        log_success(f"گام ۷.۲ (تکمیل سفارش خرید): سفارش خرید {po.po_number} پس از دریافت کامل اقلام در وضعیت COMPLETED بسته شد")


def test_5_full_matrix_get_routes(wh_id: int, prod_id: int):
    """۵. ممیزی ماتریس کامل تمام مسیرهای GET برای هر ۵ نقش سازمانی بدون ایجاد خطای ۵۰۰"""
    log_step("۵. ممیزی ماتریس کامل تمام صفحات سیستم برای هر ۵ نقش (تضمین عدم وقوع خطای ۵۰۰)")
    
    role_routes = {
        "admin": [
            "/dashboard", "/inventory/balance", "/inventory/transaction", "/inventory/transactions",
            "/inventory/transfer", "/inventory/stocktaking", "/inventory/returns/new", "/inventory/fiscal-years",
            "/purchases", "/purchases/new", "/sales", "/sales/new", "/master-data/parties",
            "/weighbridge", "/weighbridge/new", "/bagging", "/bagging/new", "/admin/users",
            "/admin/audit-logs", "/inventory/alerts"
        ],
        "finance": [
            "/dashboard", "/inventory/balance", "/inventory/transactions", "/inventory/transfer",
            "/inventory/stocktaking", "/inventory/returns/new", "/inventory/fiscal-years",
            "/purchases", "/sales", "/master-data/parties"
        ],
        "warehouse": [
            "/dashboard", "/inventory/balance", "/inventory/transaction", "/inventory/transactions",
            "/inventory/transfer", "/inventory/stocktaking", "/inventory/returns/new",
            "/bagging", "/bagging/new", "/weighbridge"
        ],
        "commercial": [
            "/dashboard", "/purchases", "/purchases/new", "/sales", "/sales/new", "/master-data/parties"
        ],
        "baskool": [
            "/dashboard", "/weighbridge", "/weighbridge/new"
        ]
    }

    for username, routes in role_routes.items():
        client = get_auth_client(username, "1234")
        for route in routes:
            res = client.get(route)
            assert res.status_code != 500, f"خطای ۵۰۰ در مسیر {route} برای نقش {username} رخ داد! متن: {res.text[:200]}"
            assert res.status_code in (200, 303), f"کد غیرمنتظره {res.status_code} در مسیر {route} برای نقش {username}"
        log_success(f"تمام {len(routes)} مسیر مجاز نقش «{username}» بدون هیچ خطای ۵۰۰ با موفقیت بارگذاری شدند")


def run_all_inspections():
    """اجرای سرتاسری تمام آزمون‌های ۵ گانه بازرس خودکار"""
    print(f"\n{CYAN}{BOLD}{'='*70}{RESET}")
    print(f"{CYAN}{BOLD}  🚀 آغاز ممیزی خودکار سامانه NexusPour Enterprise ERP (Phase 4 Inspector){RESET}")
    print(f"{CYAN}{BOLD}{'='*70}{RESET}")

    wh_id, prod_id, fy_id = setup_initial_database_fixtures()
    
    # ۱. آزمون لاگین
    test_1_user_logins()

    # ۲. آزمون RBAC
    test_2_rbac_security_barriers()

    # ۳. آزمون اختیارات تجاری بازرگانی + بررسی ویوهای جزئیات سفارش خرید و فروش
    sup_id, cust_id = test_3_commercial_actions(wh_id, prod_id)

    # ۴. آزمون چرخه کامل
    test_4_full_lifecycle_workflow(wh_id, prod_id, sup_id)

    # ۵. ممیزی ماتریسی صفحات برای هر ۵ نقش
    test_5_full_matrix_get_routes(wh_id, prod_id)

    print(f"\n{GREEN}{BOLD}{'='*70}{RESET}")
    print(f"{GREEN}{BOLD}  🎉 تمام آزمون‌های ۵ گانه با موفقیت ۱۰۰٪ پاس شدند (ALL INSPECTIONS PASSED){RESET}")
    print(f"{GREEN}{BOLD}{'='*70}{RESET}\n")


if __name__ == "__main__":
    run_all_inspections()

