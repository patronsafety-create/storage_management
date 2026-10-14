from contextlib import asynccontextmanager
import os
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from src.infrastructure.number_normalizer import NumberNormalizationMiddleware
from src.core.localization.regions import register_jinja_filters

from src.api import (
    auth, ui, inventory_ui, master_data_ui, admin_ui, stock_api, parties_ui,
    purchases_ui, sales_ui, alerts_ui, weighbridge_ui, cutting_ui, bagging_ui, compliance_ui, audit_ui
)
from src.infrastructure.database import engine, SessionLocal, Base
from src.domain_model import inventory_models, auth_models
from src.domain_model.enums import PurchaseOrderStatus, WeighbridgeStatus, CuttingStatus, BaggingStatus, DocumentStatus
from src.infrastructure.security import get_password_hash
from src.infrastructure.seed_users import seed_enterprise_users

from sqlalchemy import text

# ساخت تمام جداول دیتابیس
Base.metadata.create_all(bind=engine)

templates = Jinja2Templates(directory="templates")
register_jinja_filters(templates)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """تزریق داده‌های پایه (Seeding) و بررسی سلامت اسکیمای دیتابیس هنگام راه‌اندازی"""
    # ۱. اطمینان از اعمال تغییرات اسکیمای غیرمخرب
    try:
        if engine.dialect.name == "postgresql":
            with engine.connect() as conn:
                conn.execute(text("""
                CREATE TABLE IF NOT EXISTS product_categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    code VARCHAR UNIQUE,
                    description VARCHAR,
                    parent_id INTEGER REFERENCES product_categories(id)
                );
                CREATE INDEX IF NOT EXISTS ix_product_categories_id ON product_categories(id);

                ALTER TABLE products ADD COLUMN IF NOT EXISTS sku VARCHAR UNIQUE;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS secondary_uom VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS nominal_weight FLOAT DEFAULT 0.0;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS irc_code VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS hs_code VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS gtip_code VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS tse_standard VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS category_id INTEGER REFERENCES product_categories(id);
                ALTER TABLE products ADD COLUMN IF NOT EXISTS brand VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS size VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS length FLOAT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS thickness FLOAT;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS grade VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS standard VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS min_stock FLOAT DEFAULT 0.0;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS max_stock FLOAT DEFAULT 0.0;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS reorder_point FLOAT DEFAULT 0.0;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS description VARCHAR;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
                ALTER TABLE products ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();
                CREATE INDEX IF NOT EXISTS ix_products_sku ON products(sku);

                CREATE TABLE IF NOT EXISTS suppliers (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    code VARCHAR UNIQUE,
                    contact_person VARCHAR,
                    phone VARCHAR,
                    email VARCHAR,
                    address VARCHAR,
                    national_id VARCHAR,
                    vkn VARCHAR,
                    tax_office VARCHAR,
                    mersis_no VARCHAR,
                    country_code VARCHAR DEFAULT 'IR',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_suppliers_id ON suppliers(id);

                ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS vkn VARCHAR;
                ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS tax_office VARCHAR;
                ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS mersis_no VARCHAR;
                ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS country_code VARCHAR DEFAULT 'IR';

                CREATE TABLE IF NOT EXISTS customers (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    code VARCHAR UNIQUE,
                    contact_person VARCHAR,
                    phone VARCHAR,
                    email VARCHAR,
                    address VARCHAR,
                    national_id VARCHAR,
                    vkn VARCHAR,
                    tax_office VARCHAR,
                    mersis_no VARCHAR,
                    country_code VARCHAR DEFAULT 'IR',
                    credit_limit FLOAT DEFAULT 0.0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_customers_id ON customers(id);

                ALTER TABLE customers ADD COLUMN IF NOT EXISTS vkn VARCHAR;
                ALTER TABLE customers ADD COLUMN IF NOT EXISTS tax_office VARCHAR;
                ALTER TABLE customers ADD COLUMN IF NOT EXISTS mersis_no VARCHAR;
                ALTER TABLE customers ADD COLUMN IF NOT EXISTS country_code VARCHAR DEFAULT 'IR';

                ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS country_code VARCHAR DEFAULT 'IR';
                ALTER TABLE warehouses ADD COLUMN IF NOT EXISTS currency VARCHAR DEFAULT 'IRR';

                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS currency VARCHAR DEFAULT 'IRR';
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS exchange_rate FLOAT DEFAULT 1.0;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS supplier_id INTEGER REFERENCES suppliers(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS customer_id INTEGER REFERENCES customers(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS status VARCHAR DEFAULT 'APPROVED';
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS rejection_reason VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS approved_by_id INTEGER REFERENCES users(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS is_return BOOLEAN DEFAULT FALSE;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS return_reason VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS parent_transaction_id INTEGER REFERENCES stock_transactions(id);

                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS secondary_quantity FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS secondary_uom VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS weight_per_unit FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS standard_weight FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS deviation_percent FLOAT;

                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS freight_cost FLOAT DEFAULT 0.0;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS insurance_cost FLOAT DEFAULT 0.0;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS weighbridge_cost FLOAT DEFAULT 0.0;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS bill_of_lading_qty FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS shrinkage_qty FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS shrinkage_percent FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS allowed_tolerance_percent FLOAT DEFAULT 0.3;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS penalty_amount FLOAT DEFAULT 0.0;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS total_landed_cost FLOAT DEFAULT 0.0;

                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS heat_number VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS mtc_number VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS chemical_analysis VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS mechanical_analysis VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS chemical_nitrogen FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS chemical_biuret FLOAT;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS chemical_moisture FLOAT;

                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS waybill_number VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS tracking_code VARCHAR;

                CREATE INDEX IF NOT EXISTS ix_stock_transactions_supplier_id ON stock_transactions(supplier_id);
                CREATE INDEX IF NOT EXISTS ix_stock_transactions_customer_id ON stock_transactions(customer_id);

                CREATE TABLE IF NOT EXISTS purchase_orders (
                    id SERIAL PRIMARY KEY,
                    po_number VARCHAR NOT NULL UNIQUE,
                    supplier_id INTEGER REFERENCES suppliers(id),
                    order_date TIMESTAMPTZ DEFAULT NOW(),
                    delivery_due_date VARCHAR,
                    status VARCHAR DEFAULT 'CONFIRMED',
                    notes VARCHAR,
                    created_by_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_purchase_orders_id ON purchase_orders(id);
                CREATE INDEX IF NOT EXISTS ix_purchase_orders_po_number ON purchase_orders(po_number);

                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS subtotal_amount FLOAT DEFAULT 0.0;
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS vat_rate FLOAT DEFAULT 0.10;
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS vat_amount FLOAT DEFAULT 0.0;
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS tevkifat_rate VARCHAR;
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS tevkifat_amount FLOAT DEFAULT 0.0;
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS total_amount FLOAT DEFAULT 0.0;
                ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS currency VARCHAR DEFAULT 'IRR';

                CREATE TABLE IF NOT EXISTS purchase_order_items (
                    id SERIAL PRIMARY KEY,
                    purchase_order_id INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id),
                    quantity FLOAT NOT NULL,
                    received_quantity FLOAT DEFAULT 0.0,
                    unit_price FLOAT DEFAULT 0.0,
                    total_price FLOAT DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS ix_purchase_order_items_id ON purchase_order_items(id);

                CREATE TABLE IF NOT EXISTS weighbridge_tickets (
                    id SERIAL PRIMARY KEY,
                    ticket_number VARCHAR NOT NULL UNIQUE,
                    truck_plate VARCHAR NOT NULL,
                    driver_name VARCHAR NOT NULL,
                    driver_phone VARCHAR,
                    truck_type VARCHAR DEFAULT 'تریلی کفی ۱۸ چرخ',
                    supplier_id INTEGER REFERENCES suppliers(id),
                    customer_id INTEGER REFERENCES customers(id),
                    product_id INTEGER REFERENCES products(id),
                    warehouse_id INTEGER REFERENCES warehouses(id),
                    gross_weight FLOAT DEFAULT 0.0,
                    tare_weight FLOAT DEFAULT 0.0,
                    net_weight FLOAT DEFAULT 0.0,
                    max_allowed_weight FLOAT DEFAULT 40000.0,
                    is_overweight BOOLEAN DEFAULT FALSE,
                    status VARCHAR DEFAULT 'FIRST_WEIGHING',
                    notes VARCHAR,
                    operator_name VARCHAR,
                    stock_transaction_id INTEGER REFERENCES stock_transactions(id),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS ix_weighbridge_tickets_id ON weighbridge_tickets(id);
                CREATE INDEX IF NOT EXISTS ix_weighbridge_tickets_ticket_number ON weighbridge_tickets(ticket_number);

                CREATE TABLE IF NOT EXISTS cutting_orders (
                    id SERIAL PRIMARY KEY,
                    order_number VARCHAR NOT NULL UNIQUE,
                    product_id INTEGER REFERENCES products(id),
                    original_length FLOAT DEFAULT 12.0,
                    cut_length FLOAT NOT NULL,
                    pieces_count INTEGER DEFAULT 1,
                    remnant_length FLOAT NOT NULL,
                    remnant_weight FLOAT DEFAULT 0.0,
                    destination VARCHAR DEFAULT 'انبار ته‌شاخه‌ها',
                    status VARCHAR DEFAULT 'COMPLETED',
                    notes VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_cutting_orders_id ON cutting_orders(id);

                CREATE TABLE IF NOT EXISTS bagging_orders (
                    id SERIAL PRIMARY KEY,
                    order_number VARCHAR NOT NULL UNIQUE,
                    bulk_product_id INTEGER REFERENCES products(id),
                    packaged_product_id INTEGER REFERENCES products(id),
                    bulk_tonnage_used FLOAT NOT NULL,
                    packages_produced FLOAT NOT NULL,
                    package_type VARCHAR DEFAULT 'جامبوبگ ۱ تنی',
                    waste_tonnage FLOAT DEFAULT 0.0,
                    packaging_cost_per_ton FLOAT DEFAULT 0.0,
                    status VARCHAR DEFAULT 'COMPLETED',
                    notes VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_bagging_orders_id ON bagging_orders(id);

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    user_name VARCHAR,
                    action VARCHAR NOT NULL,
                    entity_name VARCHAR NOT NULL,
                    entity_id VARCHAR,
                    details VARCHAR,
                    ip_address VARCHAR,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs(id);

                -- فاز ۱: ارتقای اسکیمای سال مالی و سفارشات فروش
                CREATE TABLE IF NOT EXISTS fiscal_years (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE,
                    start_date VARCHAR NOT NULL,
                    end_date VARCHAR NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_closed BOOLEAN DEFAULT FALSE,
                    closed_at TIMESTAMPTZ,
                    closed_by_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_fiscal_years_id ON fiscal_years(id);

                CREATE TABLE IF NOT EXISTS sales_orders (
                    id SERIAL PRIMARY KEY,
                    so_number VARCHAR NOT NULL UNIQUE,
                    customer_id INTEGER REFERENCES customers(id),
                    order_date TIMESTAMPTZ DEFAULT NOW(),
                    delivery_due_date VARCHAR,
                    status VARCHAR DEFAULT 'CONFIRMED',
                    notes VARCHAR,
                    subtotal_amount FLOAT DEFAULT 0.0,
                    vat_rate FLOAT DEFAULT 0.10,
                    vat_amount FLOAT DEFAULT 0.0,
                    tevkifat_rate VARCHAR,
                    tevkifat_amount FLOAT DEFAULT 0.0,
                    total_amount FLOAT DEFAULT 0.0,
                    currency VARCHAR DEFAULT 'IRR',
                    created_by_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS ix_sales_orders_id ON sales_orders(id);
                CREATE INDEX IF NOT EXISTS ix_sales_orders_so_number ON sales_orders(so_number);

                CREATE TABLE IF NOT EXISTS sales_order_items (
                    id SERIAL PRIMARY KEY,
                    sales_order_id INTEGER REFERENCES sales_orders(id) ON DELETE CASCADE,
                    product_id INTEGER REFERENCES products(id),
                    quantity FLOAT NOT NULL,
                    delivered_quantity FLOAT DEFAULT 0.0,
                    unit_price FLOAT DEFAULT 0.0,
                    total_price FLOAT DEFAULT 0.0
                );
                CREATE INDEX IF NOT EXISTS ix_sales_order_items_id ON sales_order_items(id);

                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS fiscal_year_id INTEGER REFERENCES fiscal_years(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS purchase_order_id INTEGER REFERENCES purchase_orders(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS purchase_order_item_id INTEGER REFERENCES purchase_order_items(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS sales_order_id INTEGER REFERENCES sales_orders(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS sales_order_item_id INTEGER REFERENCES sales_order_items(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS weighbridge_ticket_id INTEGER REFERENCES weighbridge_tickets(id);
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS transaction_source VARCHAR;
                ALTER TABLE stock_transactions ADD COLUMN IF NOT EXISTS transaction_date TIMESTAMPTZ;

                ALTER TABLE weighbridge_tickets ADD COLUMN IF NOT EXISTS purchase_order_id INTEGER REFERENCES purchase_orders(id);
                ALTER TABLE weighbridge_tickets ADD COLUMN IF NOT EXISTS sales_order_id INTEGER REFERENCES sales_orders(id);

                CREATE INDEX IF NOT EXISTS ix_stock_transactions_fiscal_year_id ON stock_transactions(fiscal_year_id);
                CREATE INDEX IF NOT EXISTS ix_stock_transactions_purchase_order_id ON stock_transactions(purchase_order_id);
                CREATE INDEX IF NOT EXISTS ix_stock_transactions_sales_order_id ON stock_transactions(sales_order_id);
                CREATE INDEX IF NOT EXISTS ix_stock_transactions_transaction_source ON stock_transactions(transaction_source);

                -- بهینه‌سازی و انعطاف‌پذیری قید مقدار برای اصلاحات ریالی (quantity >= 0)
                DO $$
                BEGIN
                    ALTER TABLE stock_transactions DROP CONSTRAINT IF EXISTS check_quantity_positive;
                    ALTER TABLE stock_transactions DROP CONSTRAINT IF EXISTS check_quantity_non_negative;
                    ALTER TABLE stock_transactions ADD CONSTRAINT check_quantity_non_negative CHECK (quantity >= 0);
                EXCEPTION WHEN OTHERS THEN
                    NULL;
                END $$;
            """))
            conn.commit()
    except Exception as e:
        print(f"Auto-migration check notice: {e}")

    db = SessionLocal()
    try:
        # ۱. سال مالی پیش‌فرض
        if not db.query(inventory_models.FiscalYear).filter(inventory_models.FiscalYear.is_active == True).first():
            db.add(inventory_models.FiscalYear(
                name="سال مالی ۱۴۰۳",
                start_date="1403-01-01",
                end_date="1403-12-29",
                is_active=True,
                is_closed=False
            ))
            db.commit()
        # ۲. انبارهای پیش‌فرض
        if not db.query(inventory_models.Warehouse).first():
            db.add_all([
                inventory_models.Warehouse(name="انبار شماره یک (محوطه سنگین و شمش)"),
                inventory_models.Warehouse(name="انبار شماره دو (سوله مسقف و شیمیایی)")
            ])
            db.commit()

        # ۳. دسته‌بندی‌های پیش‌فرض کالاها
        if not db.query(inventory_models.ProductCategory).first():
            db.add_all([
                inventory_models.ProductCategory(name="مقاطع و شمش فولادی", code="STL-RAW", description="انواع مقاطع فولادی، شمش، بیلت و میلگرد"),
                inventory_models.ProductCategory(name="مواد شیمیایی و پتروشیمی", code="CHEM-PET", description="کودهای شیمیایی، اوره فله و بسته‌بندی"),
                inventory_models.ProductCategory(name="لوله و پروفیل صنعتی", code="STL-PIP", description="لوله‌های درزدار، مانیسمان و قوطی پروفیل"),
                inventory_models.ProductCategory(name="ملزومات بسته‌بندی و پالت", code="PKG-SUP", description="کیسه، جامبوبگ، نخ دوخت و پالت چوبی")
            ])
            db.commit()

        # ۴. کالاهای پیش‌فرض و غنی‌سازی مشخصات
        cat_steel = db.query(inventory_models.ProductCategory).filter_by(code="STL-RAW").first()
        cat_chem = db.query(inventory_models.ProductCategory).filter_by(code="CHEM-PET").first()

        if not db.query(inventory_models.Product).first():
            db.add_all([
                inventory_models.Product(
                    name="شمش فولادی ۱۵۰×۱۵۰",
                    uom="تن",
                    secondary_uom="قالب",
                    nominal_weight=2000.0,
                    sku="BLT-150-5SP-KSC",
                    irc_code="2800000140301",
                    hs_code="72071100",
                    category_id=cat_steel.id if cat_steel else None,
                    brand="فولاد خوزستان",
                    size="150x150",
                    length=6.0,
                    grade="5SP",
                    standard="ISIRI 3132",
                    min_stock=100.0,
                    reorder_point=150.0
                ),
                inventory_models.Product(
                    name="اوره گرانول صادراتی (فله)",
                    uom="تن",
                    secondary_uom="جامبوبگ",
                    nominal_weight=1000.0,
                    sku="UREA-GRAN-PRD-46",
                    irc_code="2800000140302",
                    hs_code="31021000",
                    category_id=cat_chem.id if cat_chem else None,
                    brand="پتروشیمی پردیس",
                    grade="46% Nitrogen",
                    standard="صادراتی گرید A",
                    min_stock=50.0,
                    reorder_point=80.0
                ),
                inventory_models.Product(
                    name="میلگرد آجدار سایز ۱۶ (شاخه ۱۲ متری)",
                    uom="کیلوگرم",
                    secondary_uom="شاخه",
                    nominal_weight=18.96,
                    sku="REB-A3-16-NSB",
                    irc_code="2800000140303",
                    hs_code="72142000",
                    category_id=cat_steel.id if cat_steel else None,
                    brand="فولاد نیشابور",
                    size="16",
                    length=12.0,
                    grade="A3",
                    standard="DIN 488",
                    min_stock=5000.0,
                    reorder_point=10000.0
                )
            ])
            db.commit()

        # ۵. تأمین‌کنندگان فرضی و پایه (Hypothetical Suppliers)
        if not db.query(inventory_models.Supplier).first():
            db.add_all([
                inventory_models.Supplier(
                    name="تأمین‌کننده فرضی ۱ (مجتمع فولاد مبارکه اصفهان)",
                    code="SUP-001",
                    contact_person="مهندس محمدی (واحد فروش کلاف و ورق)",
                    phone="031-52732222",
                    email="sales@msc.ir",
                    address="اصفهان، ۵۰ کیلومتری جنوب غربی اصفهان، مجتمع فولاد مبارکه",
                    national_id="10260289464",
                    is_active=True
                ),
                inventory_models.Supplier(
                    name="تأمین‌کننده فرضی ۲ (شرکت سهامی ذوب‌آهن اصفهان)",
                    code="SUP-002",
                    contact_person="آقای احمدی (مدیریت فروش مقاطع و شمش)",
                    phone="031-52573333",
                    email="info@esco.ir",
                    address="اصفهان، کیلومتر ۴۵ جاده اصفهان-شهرکرد، کارخانه ذوب‌آهن",
                    national_id="10260087451",
                    is_active=True
                ),
                inventory_models.Supplier(
                    name="تأمین‌کننده فرضی ۳ (شرکت پتروشیمی پردیس عسلویه)",
                    code="SUP-003",
                    contact_person="خانم رضایی (فروش اوره صنعتی و کشاورزی)",
                    phone="077-37292000",
                    email="commercial@pdpcomplex.com",
                    address="بوشهر، منطقه ویژه اقتصادی انرژی پارس عسلویه",
                    national_id="10102547890",
                    is_active=True
                )
            ])
            db.commit()

        # ۶. مشتریان فرضی و پایه (Hypothetical Customers)
        if not db.query(inventory_models.Customer).first():
            db.add_all([
                inventory_models.Customer(
                    name="مشتری فرضی ۱ (پروژه ساختمانی برج آرمان امید)",
                    code="CUST-001",
                    contact_person="مهندس پورمحمود (سرپرست کارگاه سازه)",
                    phone="021-88776655",
                    email="arman_project@nexus.ir",
                    address="تهران، بزرگراه همت، پروژه برج تجاری مسکونی آرمان",
                    national_id="14008954712",
                    credit_limit=50000000000.0,
                    is_active=True
                ),
                inventory_models.Customer(
                    name="مشتری فرضی ۲ (شرکت مهندسی و توسعه خطوط لوله پارس)",
                    code="CUST-002",
                    contact_person="مهندس کریمی (مدیریت تأمین تجهیزات)",
                    phone="021-22334455",
                    email="procurement@parspipeline.com",
                    address="تهران، خیابان ولیعصر، برج پارس",
                    national_id="10103214569",
                    credit_limit=80000000000.0,
                    is_active=True
                ),
                inventory_models.Customer(
                    name="مشتری فرضی ۳ (بازرگانی صنایع فلزی کاوه)",
                    code="CUST-003",
                    contact_person="حاج‌آقا کاویانی (مدیر خرید بازار آهن شادآباد)",
                    phone="021-66554433",
                    email="kaveh_steel@gmail.com",
                    address="تهران، بازار آهن شادآباد، بلوار طاووس، پلاک ۲۴",
                    national_id="10100987654",
                    credit_limit=30000000000.0,
                    is_active=True
                )
            ])
            db.commit()

        # ۶-ب. تأمین‌کنندگان شاخص ترکیه (Turkish Key Industry Suppliers)
        if not db.query(inventory_models.Supplier).filter_by(code="TR-SUP-001").first():
            db.add_all([
                inventory_models.Supplier(
                    name="Ereğli Demir ve Çelik Fabrikaları T.A.Ş. (Erdemir)",
                    code="TR-SUP-001",
                    contact_person="Ahmet Yılmaz (Satış & Lojistik Müdürü)",
                    phone="03723232500",
                    email="satis@erdemir.com.tr",
                    address="Kdz. Ereğli, Zonguldak, Türkiye",
                    national_id="3530018590",
                    vkn="3530018590",
                    tax_office="Karadeniz Ereğli Vergi Dairesi",
                    mersis_no="0353001859000018",
                    country_code="TR",
                    is_active=True
                ),
                inventory_models.Supplier(
                    name="İskenderun Demir ve Çelik A.Ş. (İsdemir)",
                    code="TR-SUP-002",
                    contact_person="Mehmet Demir (Kütük & Çubuk Satış Direktörü)",
                    phone="03267584000",
                    email="pazarlama@isdemir.com.tr",
                    address="Payas, İskenderun, Hatay, Türkiye",
                    national_id="4810052415",
                    vkn="4810052415",
                    tax_office="İskenderun Vergi Dairesi",
                    mersis_no="0481005241500012",
                    country_code="TR",
                    is_active=True
                ),
                inventory_models.Supplier(
                    name="Karabük Demir Çelik Sanayi ve Ticaret A.Ş. (Kardemir)",
                    code="TR-SUP-003",
                    contact_person="Murat Kaya (Profil ve Ray Sevkiyat Şefi)",
                    phone="03704182000",
                    email="kurumsal@kardemir.com",
                    address="Karabük Merkez, Karabük, Türkiye",
                    national_id="5240031891",
                    vkn="5240031891",
                    tax_office="Karabük Vergi Dairesi",
                    mersis_no="0524003189100015",
                    country_code="TR",
                    is_active=True
                ),
                inventory_models.Supplier(
                    name="Toros Tarım ve Gübre Sanayi A.Ş. (Toros Gübre)",
                    code="TR-SUP-004",
                    contact_person="Fatma Çelik (Kimyevi Gübre & Üre Satış Yöneticisi)",
                    phone="02123570202",
                    email="toros@toros.com.tr",
                    address="Tekfen Tower, Levent, İstanbul, Türkiye",
                    national_id="8510041233",
                    vkn="8510041233",
                    tax_office="Büyük Mükellefler Vergi Dairesi",
                    mersis_no="0851004123300016",
                    country_code="TR",
                    is_active=True
                )
            ])
            db.commit()

        # ۶-ج. مشتریان و پیمانکاران شاخص ترکیه (Turkish Key Industry Customers)
        if not db.query(inventory_models.Customer).filter_by(code="TR-CUST-001").first():
            db.add_all([
                inventory_models.Customer(
                    name="Rönesans Holding / İnşaat Sanayi ve Ticaret A.Ş.",
                    code="TR-CUST-001",
                    contact_person="Emre Şahin (Satın Alma ve Şantiye Tedarik Direktörü)",
                    phone="03124413141",
                    email="tedarik@ronesans.com",
                    address="Çankaya, Ankara, Türkiye",
                    national_id="7350021940",
                    vkn="7350021940",
                    tax_office="Başkent Vergi Dairesi",
                    mersis_no="0735002194000019",
                    country_code="TR",
                    credit_limit=15000000.0,
                    is_active=True
                ),
                inventory_models.Customer(
                    name="ENKA İnşaat ve Sanayi A.Ş.",
                    code="TR-CUST-002",
                    contact_person="Hakan Arslan (Endüstriyel Projeler Satın Alma)",
                    phone="02123761000",
                    email="procurement@enka.com",
                    address="Balmumcu, Beşiktaş, İstanbul, Türkiye",
                    national_id="3360018422",
                    vkn="3360018422",
                    tax_office="Beşiktaş Vergi Dairesi",
                    mersis_no="0336001842200014",
                    country_code="TR",
                    credit_limit=25000000.0,
                    is_active=True
                ),
                inventory_models.Customer(
                    name="Marmara Çelik Profil ve Dış Ticaret Ltd. Şti.",
                    code="TR-CUST-003",
                    contact_person="Ali Öztürk (Depo ve Dış Ticaret Müdürü)",
                    phone="02164998877",
                    email="info@marmaracelik.com.tr",
                    address="Dudullu Organize Sanayi Bölgesi, Ümraniye, İstanbul",
                    national_id="6120048192",
                    vkn="6120048192",
                    tax_office="Ümraniye Vergi Dairesi",
                    mersis_no="0612004819200011",
                    country_code="TR",
                    credit_limit=8000000.0,
                    is_active=True
                )
            ])
            db.commit()

        # ۶-د. کالاهای شاخص صنایع ترکیه (Turkish Steel & Chemical Products with GTİP & TSE)
        if not db.query(inventory_models.Product).filter_by(sku="TR-REB-B420B-16").first():
            cat_steel = db.query(inventory_models.ProductCategory).filter_by(code="STL-RAW").first()
            cat_chem = db.query(inventory_models.ProductCategory).filter_by(code="CHEM-PET").first()
            db.add_all([
                inventory_models.Product(
                    name="Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
                    uom="kg",
                    secondary_uom="çubuk",
                    nominal_weight=18.96,
                    sku="TR-REB-B420B-16",
                    gtip_code="7214.20.00.00.00",
                    tse_standard="TS 708",
                    hs_code="72142000",
                    category_id=cat_steel.id if cat_steel else None,
                    brand="İsdemir",
                    size="16",
                    length=12.0,
                    grade="B420B",
                    standard="TS 708 / TS EN 10080",
                    min_stock=5000.0,
                    reorder_point=10000.0,
                    description="Standart nervürlü inşaat çeliği (TS 708 B420B)"
                ),
                inventory_models.Product(
                    name="Sürekli Döküm Çelik Kütük 150×150mm S235JR",
                    uom="ton",
                    secondary_uom="kütük",
                    nominal_weight=2000.0,
                    sku="TR-BLT-150-S235JR",
                    gtip_code="7207.11.14.00.00",
                    tse_standard="TS EN 10025-2",
                    hs_code="72071114",
                    category_id=cat_steel.id if cat_steel else None,
                    brand="Kardemir",
                    size="150x150",
                    length=6.0,
                    grade="S235JR",
                    standard="TS EN 10025-2",
                    min_stock=100.0,
                    reorder_point=200.0,
                    description="Sürekli döküm yapı çeliği kare kütük"
                ),
                inventory_models.Product(
                    name="Granül Üre Gübresi %46 Azot (Dökme & Big Bag)",
                    uom="ton",
                    secondary_uom="big-bag",
                    nominal_weight=1000.0,
                    sku="TR-UREA-GRAN-46",
                    gtip_code="3102.10.10.00.00",
                    tse_standard="TS 3601",
                    hs_code="31021010",
                    category_id=cat_chem.id if cat_chem else None,
                    brand="Toros Gübre",
                    grade="%46 N",
                    standard="TS 3601 / EC FERTILIZER",
                    min_stock=50.0,
                    reorder_point=100.0,
                    description="Tarımsal ve endüstriyel saf granül üre gübresi"
                )
            ])
            db.commit()

        # ۷. سفارشات خرید فرضی و پایه (Hypothetical Purchase Orders)
        sup1 = db.query(inventory_models.Supplier).first()
        prod1 = db.query(inventory_models.Product).first()
        if not db.query(inventory_models.PurchaseOrder).first() and sup1 and prod1:
            po1 = inventory_models.PurchaseOrder(
                po_number="PO-1403-0001",
                supplier_id=sup1.id,
                delivery_due_date="۱۴۰۳/۰۸/۲۵",
                status=PurchaseOrderStatus.CONFIRMED,
                notes="قرارداد خرید شمش تحویل درب کارخانه با شرط آزمون کوانتومتری"
            )
            db.add(po1)
            db.flush()
            db.add(inventory_models.PurchaseOrderItem(
                purchase_order_id=po1.id,
                product_id=prod1.id,
                quantity=100.0,
                received_quantity=0.0,
                unit_price=275000000.0,
                total_price=27500000000.0
            ))
            db.commit()

        # ۸. قبوض باسکول فرضی (Hypothetical Weighbridge Tickets)
        w1 = db.query(inventory_models.Warehouse).first()
        if not db.query(inventory_models.WeighbridgeTicket).first() and prod1 and w1:
            db.add_all([
                inventory_models.WeighbridgeTicket(
                    ticket_number="WB-1403-0001",
                    truck_plate="ایران ۶۸ - ۳۴۵ ع ۱۲",
                    driver_name="محمد صادقی",
                    driver_phone="09121112233",
                    truck_type="تریلی کفی ۱۸ چرخ",
                    product_id=prod1.id,
                    warehouse_id=w1.id,
                    supplier_id=sup1.id if sup1 else None,
                    gross_weight=38500.0,
                    tare_weight=14200.0,
                    net_weight=24300.0,
                    max_allowed_weight=40000.0,
                    is_overweight=False,
                    status=WeighbridgeStatus.COMPLETED,
                    operator_name="متصدی باسکول شیفت صبح",
                    notes="توزین استاندارد بدون مغایرت بارنامه",
                    completed_at=datetime.now(timezone.utc)
                ),
                inventory_models.WeighbridgeTicket(
                    ticket_number="WB-1403-0002",
                    truck_plate="ایران ۱۱ - ۷۸۹ ب ۴۵",
                    driver_name="علی اکبری",
                    driver_phone="09132223344",
                    truck_type="کمپرسی سنگین",
                    product_id=prod1.id,
                    warehouse_id=w1.id,
                    supplier_id=sup1.id if sup1 else None,
                    gross_weight=39200.0,
                    tare_weight=0.0,
                    net_weight=0.0,
                    max_allowed_weight=40000.0,
                    is_overweight=False,
                    status=WeighbridgeStatus.FIRST_WEIGHING,
                    operator_name="متصدی شیفت",
                    notes="در حال تخلیه در محوطه انبار شماره یک"
                )
            ])
            db.commit()

        # ۹. دستورات برش و انبار ته‌شاخه فرضی (Hypothetical Cutting Orders)
        if not db.query(inventory_models.CuttingOrder).first() and prod1:
            db.add(inventory_models.CuttingOrder(
                order_number="CUT-1403-0001",
                product_id=prod1.id,
                original_length=12.0,
                cut_length=4.5,
                pieces_count=2,
                remnant_length=3.0,
                remnant_weight=56.88,
                destination="انبار ته‌شاخه‌ها",
                status=CuttingStatus.COMPLETED,
                notes="برش سفارشی پروژه ستون‌های سازه آرمان"
            ))
            db.commit()

        # ۱۰. دستور کیسه‌گیری فله به جامبوبگ اوره (Hypothetical Bagging Orders)
        prod_urea = db.query(inventory_models.Product).filter(inventory_models.Product.name.like("%اوره%")).first()
        if not db.query(inventory_models.BaggingOrder).first() and prod_urea:
            db.add(inventory_models.BaggingOrder(
                order_number="BAG-1403-0001",
                bulk_product_id=prod_urea.id,
                packaged_product_id=prod_urea.id,
                bulk_tonnage_used=50.0,
                packages_produced=50.0,
                package_type="جامبوبگ ۱ تنی",
                waste_tonnage=0.15,
                packaging_cost_per_ton=350000.0,
                status=BaggingStatus.COMPLETED,
                notes="عملیات کیسه‌گیری پارت صادراتی بندرعباس"
            ))
            db.commit()

        # ۱۱. ایجاد خودکار ۷ نقش و کاربر تستی با رمز عبور ۱۲۳۴ (RBAC Seed)
        seed_enterprise_users(db)
        
        # ۱۲. تزریق جامع و خودکار سناریوها و داده‌های نمونه تخصصی آهن‌آلات، میلگردها، تیرآهن، شمش، اوره و طرف‌های تجاری
        try:
            from scripts.seed_demo_data import seed_database
            seed_database(db)
        except Exception as seed_err:
            print(f"Demo seed notice: {seed_err}")

        db.commit()
    finally:
        db.close()
    yield


app = FastAPI(
    title="NexusPour ERP API",
    description="سامانه یکپارچه انبارداری نکسوس‌پور (NexusPour ERP) — طراحی و مهندسی: امید پورمحمود",
    version="2.0.0",
    lifespan=lifespan
)

# میدل‌ویر سراسری نرمال‌سازی اعداد فارسی، عربی و ممیز ترکی
app.add_middleware(NumberNormalizationMiddleware)

# ثبت سراسری فیلترهای بومی‌سازی دو زبانه (format_date, tr_loc, format_currency) در تمام قالب‌ها
for router_mod in [auth, ui, inventory_ui, master_data_ui, admin_ui, parties_ui, purchases_ui, sales_ui, alerts_ui, weighbridge_ui, cutting_ui, bagging_ui, compliance_ui, audit_ui]:
    if hasattr(router_mod, "templates"):
        register_jinja_filters(router_mod.templates)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 401:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse(
        request=request,
        name="error.html",
        context={"request": request, "status_code": exc.status_code, "detail": exc.detail},
        status_code=exc.status_code
    )


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ثبت کلیه روترهای سامانه نکسوس‌پور
app.include_router(auth.router)
app.include_router(ui.router)
app.include_router(inventory_ui.router)
app.include_router(master_data_ui.router)
app.include_router(parties_ui.router)
app.include_router(purchases_ui.router)
app.include_router(sales_ui.router)
app.include_router(weighbridge_ui.router)
app.include_router(cutting_ui.router)
app.include_router(bagging_ui.router)
app.include_router(alerts_ui.router)
app.include_router(compliance_ui.router)
app.include_router(audit_ui.router)
app.include_router(admin_ui.router)
app.include_router(stock_api.router)


@app.get("/", tags=["General"])
def read_root():
    return RedirectResponse(url="/dashboard")