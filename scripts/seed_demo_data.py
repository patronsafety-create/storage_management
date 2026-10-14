"""
اسکریپت تزریق جامع داده‌های آزمایشی و سناریوهای واقعی آهن‌آلات و پتروشیمی
NexusPour ERP - Comprehensive Demo Seeding Engine
پشتیبانی کامل از دو زبانه (فارسی و ترکی استانداردهای TSE و GİB)
"""
import sys
import os
from datetime import datetime, timedelta

# افزودن مسیر ریشه پروژه به sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from src.infrastructure.database import SessionLocal, Base, engine
from src.domain_model import inventory_models, auth_models
from src.domain_model.inventory_models import TransactionType
from src.domain_model.enums import (
    DocumentStatus, PurchaseOrderStatus,
    WeighbridgeStatus, CuttingStatus, BaggingStatus
)


def seed_database(db: Session):
    print("=" * 60)
    print("🚀 آغاز فرآیند تزریق داده‌های نمونه و سناریوهای واقعی NexusPour ERP")
    print("=" * 60)

    # ----------------------------------------------------
    # ۱. دسته‌بندی‌های کالا (Product Categories)
    # ----------------------------------------------------
    categories_data = [
        {"name": "مقاطع و شمش فولادی", "code": "STL-RAW", "desc": "انواع شمش بیلت، بلوم، اسلب و مقاطع اولیه نورد"},
        {"name": "میلگرد و آرماتور", "code": "STL-REB", "desc": "انواع میلگرد آجدار ساختمانی و کلاف صنعتی"},
        {"name": "تیرآهن و مقاطع ساختمانی", "code": "STL-BEAM", "desc": "انواع تیرآهن IPE، IPB، هاش و ناودانی"},
        {"name": "ورق و کلاف گرم", "code": "STL-FLAT", "desc": "کلاف گرم HRC، ورق سیاه، روغنی و گالوانیزه"},
        {"name": "مواد شیمیایی و پتروشیمی", "code": "CHEM-PET", "desc": "کودهای نیتروژنه، اوره گرانول فله و جامبوبگ"},
        {"name": "ملزومات بسته‌بندی و پالت", "code": "PKG-SUP", "desc": "کیسه جامبوبگ، تسمه بسته‌بندی و پالت چوبی"},
        {"name": "ضایعات و بازیافت", "code": "SCRAP-REC", "desc": "قراضه سنگین ذوبی، ته‌شاخه و پرتی نورد"}
    ]
    categories = {}
    for cat_info in categories_data:
        cat = db.query(inventory_models.ProductCategory).filter_by(code=cat_info["code"]).first()
        if not cat:
            cat = inventory_models.ProductCategory(
                name=cat_info["name"],
                code=cat_info["code"],
                description=cat_info["desc"]
            )
            db.add(cat)
            db.flush()
        categories[cat_info["code"]] = cat
    print("✓ دسته‌بندی‌های کالا آماده شد.")

    # ----------------------------------------------------
    # ۲. انبارها (Warehouses)
    # ----------------------------------------------------
    warehouses_data = [
        "انبار شماره یک (محوطه سنگین و شمش)",
        "انبار شماره دو (سوله مسقف و شیمیایی)",
        "انبار روباز تیرآهن و میلگرد",
        "انبار مرکزی تهران",
        "انبار ته‌شاخه‌ها"
    ]
    warehouses = {}
    for w_name in warehouses_data:
        w = db.query(inventory_models.Warehouse).filter_by(name=w_name).first()
        if not w:
            w = inventory_models.Warehouse(name=w_name)
            db.add(w)
            db.flush()
        warehouses[w_name] = w
    print("✓ انبارهای سازمان آماده شدند.")

    # ----------------------------------------------------
    # ۳. کاتالوگ کالاهای تخصصی آهن‌آلات، شمش، تیرآهن و اوره
    # ----------------------------------------------------
    products_data = [
        # --- شمش فولادی ---
        {
            "name": "شمش فولادی ۱۵۰×۱۵۰",
            "uom": "تن",
            "secondary_uom": "قالب",
            "nominal_weight": 2000.0,
            "sku": "BLT-150-5SP-KSC",
            "irc_code": "2800000140301",
            "hs_code": "72071100",
            "gtip_code": "7207.11.14.00.00",
            "tse_standard": "TS EN 10025-2",
            "category": categories["STL-RAW"],
            "brand": "فولاد خوزستان",
            "size": "150x150",
            "length": 6.0,
            "grade": "5SP",
            "standard": "ISIRI 3132 / S235JR",
            "min_stock": 100.0,
            "reorder_point": 200.0,
            "desc": "شمش بیلت فولادی پیوسته کوره قوس الکتریکی گرید 5SP"
        },
        {
            "name": "شمش فولادی ۱۳۰×۱۳۰",
            "uom": "تن",
            "secondary_uom": "قالب",
            "nominal_weight": 1500.0,
            "sku": "BLT-130-3SP-ESCO",
            "irc_code": "2800000140302",
            "hs_code": "72071100",
            "gtip_code": "7207.11.11.00.00",
            "tse_standard": "TS EN 10025-2",
            "category": categories["STL-RAW"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "130x130",
            "length": 6.0,
            "grade": "3SP",
            "standard": "GOST 380",
            "min_stock": 80.0,
            "reorder_point": 150.0,
            "desc": "شمش بیلت نورد گرم گرید 3SP ویژه تولید میلگرد"
        },
        # --- میلگرد آجدار در سایزهای مختلف ---
        {
            "name": "میلگرد آجدار سایز ۱۴ (شاخه ۱۲ متری)",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 14.52,
            "sku": "REB-A3-14-ESCO",
            "irc_code": "2800000140314",
            "hs_code": "72142000",
            "gtip_code": "7214.20.00.00.00",
            "tse_standard": "TS 708",
            "category": categories["STL-REB"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "14",
            "length": 12.0,
            "grade": "A3 / B420B",
            "standard": "DIN 488 / TS 708",
            "min_stock": 5000.0,
            "reorder_point": 10000.0,
            "desc": "میلگرد آجدار با مقاومت کششی بالا جهت اسکلت بتنی"
        },
        {
            "name": "میلگرد آجدار سایز ۱۶ (شاخه ۱۲ متری)",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 18.96,
            "sku": "REB-A3-16-NSB",
            "irc_code": "2800000140316",
            "hs_code": "72142000",
            "gtip_code": "7214.20.00.00.00",
            "tse_standard": "TS 708",
            "category": categories["STL-REB"],
            "brand": "فولاد نیشابور",
            "size": "16",
            "length": 12.0,
            "grade": "A3 / B420B",
            "standard": "ISIRI 3132",
            "min_stock": 5000.0,
            "reorder_point": 12000.0,
            "desc": "میلگرد آجدار شاخه‌ای نیشابور"
        },
        {
            "name": "میلگرد آجدار سایز ۱۸ (شاخه ۱۲ متری)",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 24.00,
            "sku": "REB-A3-18-ESCO",
            "irc_code": "2800000140318",
            "hs_code": "72142000",
            "gtip_code": "7214.20.00.00.00",
            "tse_standard": "TS 708",
            "category": categories["STL-REB"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "18",
            "length": 12.0,
            "grade": "A3 / B420B",
            "standard": "TS 708 / DIN 488",
            "min_stock": 4000.0,
            "reorder_point": 8000.0,
            "desc": "میلگرد آجدار ساختمانی استاندارد ذوب‌آهن اصفهان"
        },
        {
            "name": "میلگرد آجدار سایز ۲۰ (شاخه ۱۲ متری)",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 29.64,
            "sku": "REB-A3-20-KSC",
            "irc_code": "2800000140320",
            "hs_code": "72142000",
            "gtip_code": "7214.20.00.00.00",
            "tse_standard": "TS 708",
            "category": categories["STL-REB"],
            "brand": "فولاد خوزستان",
            "size": "20",
            "length": 12.0,
            "grade": "A3 / B420B",
            "standard": "TS 708",
            "min_stock": 3000.0,
            "reorder_point": 6000.0,
            "desc": "میلگرد سنگین آرماتوربندی فونداسیون"
        },
        # --- تیرآهن‌های ساختمانی IPE ---
        {
            "name": "تیرآهن IPE 14",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 154.8,
            "sku": "BM-IPE-140-ESCO",
            "irc_code": "2800000140334",
            "hs_code": "72163110",
            "gtip_code": "7216.31.10.00.00",
            "tse_standard": "TS EN 10034",
            "category": categories["STL-BEAM"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "IPE 14",
            "length": 12.0,
            "grade": "ST37-2 / S235JR",
            "standard": "DIN 1025 / TS EN 10034",
            "min_stock": 5000.0,
            "reorder_point": 10000.0,
            "desc": "پروفیل بال نیم‌پهن موازی IPE 140 استاندارد اروپا"
        },
        {
            "name": "تیرآهن IPE 16",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 189.6,
            "sku": "BM-IPE-160-ESCO",
            "irc_code": "2800000140336",
            "hs_code": "72163110",
            "gtip_code": "7216.31.10.00.00",
            "tse_standard": "TS EN 10034",
            "category": categories["STL-BEAM"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "IPE 16",
            "length": 12.0,
            "grade": "ST37-2 / S235JR",
            "standard": "TS EN 10034",
            "min_stock": 4000.0,
            "reorder_point": 8000.0,
            "desc": "تیرآهن شاخه ۱۲ متری کارخانه ذوب‌آهن اصفهان"
        },
        {
            "name": "تیرآهن IPE 18",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 225.6,
            "sku": "BM-IPE-180-ESCO",
            "irc_code": "2800000140338",
            "hs_code": "72163110",
            "gtip_code": "7216.31.10.00.00",
            "tse_standard": "TS EN 10034",
            "category": categories["STL-BEAM"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "IPE 18",
            "length": 12.0,
            "grade": "ST37-2 / S235JR",
            "standard": "TS EN 10034 / DIN 1025",
            "min_stock": 3000.0,
            "reorder_point": 7000.0,
            "desc": "تیرآهن سنگین سازه‌ای ستون و پل باربر"
        },
        {
            "name": "تیرآهن IPE 20",
            "uom": "کیلوگرم",
            "secondary_uom": "شاخه",
            "nominal_weight": 268.8,
            "sku": "BM-IPE-200-ESCO",
            "irc_code": "2800000140340",
            "hs_code": "72163110",
            "gtip_code": "7216.31.10.00.00",
            "tse_standard": "TS EN 10034",
            "category": categories["STL-BEAM"],
            "brand": "ذوب‌آهن اصفهان",
            "size": "IPE 20",
            "length": 12.0,
            "grade": "ST37-2 / S235JR",
            "standard": "TS EN 10034",
            "min_stock": 2000.0,
            "reorder_point": 5000.0,
            "desc": "تیرآهن سنگین ساختمانی سقف و اسکلت فلزی"
        },
        # --- اوره و فرآورده‌های پتروشیمی ---
        {
            "name": "اوره گرانول صادراتی (فله)",
            "uom": "تن",
            "secondary_uom": "جامبوبگ",
            "nominal_weight": 1000.0,
            "sku": "UREA-GRAN-PRD-46",
            "irc_code": "2800000140303",
            "hs_code": "31021000",
            "gtip_code": "3102.10.10.00.00",
            "tse_standard": "TS 3601",
            "category": categories["CHEM-PET"],
            "brand": "پتروشیمی پردیس",
            "grade": "46% Nitrogen",
            "standard": "TS 3601 / EC FERTILIZER",
            "min_stock": 50.0,
            "reorder_point": 100.0,
            "desc": "کود اوره گرانول صادراتی با حداقل خلوص ۴۶ درصد نیتروژن"
        },
        {
            "name": "کود اوره گرانول ۴۶ درصد ازت (جامبوبگ ۱ تنی)",
            "uom": "تن",
            "secondary_uom": "جامبوبگ",
            "nominal_weight": 1000.0,
            "sku": "UREA-BAG-1T-PRD",
            "irc_code": "2800000140304",
            "hs_code": "31021000",
            "gtip_code": "3102.10.10.00.00",
            "tse_standard": "TS 3601",
            "category": categories["CHEM-PET"],
            "brand": "پتروشیمی پردیس",
            "grade": "46% Nitrogen",
            "standard": "TS 3601",
            "min_stock": 40.0,
            "reorder_point": 80.0,
            "desc": "کود اوره گرانول بسته‌بندی شده در کیسه‌های مقاوم ۱۰۰۰ کیلوگرمی"
        },
        # --- کلاف گرم و ورق سیاه ---
        {
            "name": "کلاف گرم فولادی (ورق سیاه رول HRC)",
            "uom": "تن",
            "secondary_uom": "رول",
            "nominal_weight": 18500.0,
            "sku": "HRC-COIL-MSC-ST37",
            "irc_code": "2800000140350",
            "hs_code": "72083800",
            "gtip_code": "7208.38.00.00.00",
            "tse_standard": "TS EN 10025-2",
            "category": categories["STL-FLAT"],
            "brand": "فولاد مبارکه",
            "size": "عرض ۱۲۵۰ میل",
            "thickness": 3.0,
            "grade": "ST37 / S235JR",
            "standard": "DIN 17100 / TS EN 10025",
            "min_stock": 30.0,
            "reorder_point": 60.0,
            "desc": "کلاف ورق نورد گرم فولاد مبارکه ضخامت ۳ میلی‌متر"
        },
        {
            "name": "ورق سیاه برشی فولادی (شیت ۱۰ میل)",
            "uom": "کیلوگرم",
            "secondary_uom": "ورق",
            "nominal_weight": 471.0,
            "sku": "SHT-10MM-MSC-ST37",
            "irc_code": "2800000140352",
            "hs_code": "72085120",
            "gtip_code": "7208.51.20.00.00",
            "tse_standard": "TS EN 10025",
            "category": categories["STL-FLAT"],
            "brand": "فولاد مبارکه",
            "size": "1500x6000",
            "length": 6.0,
            "thickness": 10.0,
            "grade": "ST37",
            "standard": "ISIRI 3132",
            "min_stock": 2000.0,
            "reorder_point": 5000.0,
            "desc": "شیت ورق برشی ۱۰ میل ابعاد ۱.۵ در ۶ متر"
        },
        {
            "name": "قراضه سنگین ذوبی (ویژه)",
            "uom": "تن",
            "secondary_uom": "تن",
            "nominal_weight": 1000.0,
            "sku": "SCRAP-HMS1-HVY",
            "hs_code": "72044910",
            "gtip_code": "7204.49.10.00.00",
            "tse_standard": "TS 10582",
            "category": categories["SCRAP-REC"],
            "brand": "فولاد خوزستان",
            "grade": "HMS 1",
            "standard": "ISIRI 2883",
            "min_stock": 50.0,
            "reorder_point": 100.0,
            "desc": "قراضه آهن سنگین درجه یک مخصوص شارژ کوره ذوب"
        }
    ]

    products = {}
    for p_info in products_data:
        p = db.query(inventory_models.Product).filter_by(sku=p_info["sku"]).first()
        if not p:
            p = db.query(inventory_models.Product).filter_by(name=p_info["name"]).first()
        if not p:
            p = inventory_models.Product(
                name=p_info["name"],
                uom=p_info["uom"],
                secondary_uom=p_info.get("secondary_uom"),
                nominal_weight=p_info.get("nominal_weight", 0.0),
                sku=p_info["sku"],
                irc_code=p_info.get("irc_code"),
                hs_code=p_info.get("hs_code"),
                gtip_code=p_info.get("gtip_code"),
                tse_standard=p_info.get("tse_standard"),
                category_id=p_info["category"].id if p_info.get("category") else None,
                brand=p_info.get("brand"),
                size=p_info.get("size"),
                length=p_info.get("length"),
                thickness=p_info.get("thickness"),
                grade=p_info.get("grade"),
                standard=p_info.get("standard"),
                min_stock=p_info.get("min_stock", 0.0),
                reorder_point=p_info.get("reorder_point", 0.0),
                description=p_info.get("desc")
            )
            db.add(p)
            db.flush()
        products[p.sku] = p
        products[p.name] = p
    print(f"✓ تعداد {len(products_data)} کالای تخصصی فولادی و پتروشیمی آماده شدند.")

    # ----------------------------------------------------
    # ۴. طرف‌های تجاری (تأمین‌کنندگان و خریداران ایران و ترکیه)
    # ----------------------------------------------------
    suppliers_data = [
        {
            "name": "شرکت سهامی ذوب‌آهن اصفهان",
            "code": "SUP-002",
            "contact_person": "مهندس احمدی (واحد فروش مقاطع و شمش)",
            "phone": "031-52573333",
            "email": "sales@esco.ir",
            "address": "اصفهان، کیلومتر ۴۵ جاده اصفهان-شهرکرد، کارخانه ذوب‌آهن",
            "national_id": "10260087451",
            "country_code": "IR"
        },
        {
            "name": "مجتمع فولاد مبارکه اصفهان",
            "code": "SUP-001",
            "contact_person": "مهندس محمدی (فروش ورق و کلاف)",
            "phone": "031-52732222",
            "email": "sales@msc.ir",
            "address": "اصفهان، ۵۰ کیلومتری جنوب غربی اصفهان، مجتمع فولاد مبارکه",
            "national_id": "10260289464",
            "country_code": "IR"
        },
        {
            "name": "شرکت پتروشیمی پردیس عسلویه",
            "code": "SUP-003",
            "contact_person": "خانم رضایی (فروش اوره صادراتی)",
            "phone": "077-37292000",
            "email": "commercial@pdpcomplex.com",
            "address": "بوشهر، منطقه ویژه اقتصادی انرژی پارس عسلویه",
            "national_id": "10102547890",
            "country_code": "IR"
        },
        {
            "name": "شرکت فولاد خوزستان",
            "code": "SUP-004",
            "contact_person": "مهندس کیانی (فروش شمش و اسلب)",
            "phone": "061-32132000",
            "email": "sales@ksc.ir",
            "address": "اهواز، کیلومتر ۱۰ جاده بندر امام خمینی",
            "national_id": "10860678912",
            "country_code": "IR"
        },
        {
            "name": "Ereğli Demir ve Çelik Fabrikaları T.A.Ş. (Erdemir)",
            "code": "TR-SUP-001",
            "contact_person": "Ahmet Yılmaz (Satış & Lojistik Müdürü)",
            "phone": "03723232500",
            "email": "satis@erdemir.com.tr",
            "address": "Kdz. Ereğli, Zonguldak, Türkiye",
            "national_id": "3530018590",
            "vkn": "3530018590",
            "tax_office": "Karadeniz Ereğli Vergi Dairesi",
            "mersis_no": "0353001859000018",
            "country_code": "TR"
        },
        {
            "name": "İskenderun Demir ve Çelik A.Ş. (İsdemir)",
            "code": "TR-SUP-002",
            "contact_person": "Mehmet Demir (Kütük & Çubuk Satış Direktörü)",
            "phone": "03267584000",
            "email": "pazarlama@isdemir.com.tr",
            "address": "Payas, İskenderun, Hatay, Türkiye",
            "national_id": "4810052415",
            "vkn": "4810052415",
            "tax_office": "İskenderun Vergi Dairesi",
            "mersis_no": "0481005241500012",
            "country_code": "TR"
        },
        {
            "name": "Karabük Demir Çelik Sanayi ve Ticaret A.Ş. (Kardemir)",
            "code": "TR-SUP-003",
            "contact_person": "Murat Kaya (Profil ve Ray Sevkiyat Şefi)",
            "phone": "03704182000",
            "email": "kurumsal@kardemir.com",
            "address": "Karabük Merkez, Karabük, Türkiye",
            "national_id": "5240031891",
            "vkn": "5240031891",
            "tax_office": "Karabük Vergi Dairesi",
            "mersis_no": "0524003189100015",
            "country_code": "TR"
        },
        {
            "name": "Toros Tarım ve Gübre Sanayi A.Ş. (Toros Gübre)",
            "code": "TR-SUP-004",
            "contact_person": "Fatma Çelik (Kimyevi Gübre & Üre Satış Yöneticisi)",
            "phone": "02123570202",
            "email": "toros@toros.com.tr",
            "address": "Tekfen Tower, Levent, İstanbul, Türkiye",
            "national_id": "8510041233",
            "vkn": "8510041233",
            "tax_office": "Büyük Mükellefler Vergi Dairesi",
            "mersis_no": "0851004123300016",
            "country_code": "TR"
        }
    ]
    suppliers = {}
    for sup_info in suppliers_data:
        s = db.query(inventory_models.Supplier).filter_by(code=sup_info["code"]).first()
        if not s:
            s = inventory_models.Supplier(**sup_info)
            db.add(s)
            db.flush()
        suppliers[sup_info["code"]] = s
        suppliers[sup_info["name"]] = s
    print("✓ تأمین‌کنندگان شاخص صنایع فولاد و شیمیایی ایران و ترکیه آماده شدند.")

    customers_data = [
        {
            "name": "پروژه ساختمانی برج آرمان امید",
            "code": "CUST-001",
            "contact_person": "مهندس پورمحمود (سرپرست کارگاه سازه)",
            "phone": "021-88776655",
            "email": "arman_project@nexus.ir",
            "address": "تهران، بزرگراه همت، پروژه برج تجاری مسکونی آرمان",
            "national_id": "14008954712",
            "credit_limit": 50000000000.0,
            "country_code": "IR"
        },
        {
            "name": "شرکت مهندسی و توسعه خطوط لوله پارس",
            "code": "CUST-002",
            "contact_person": "مهندس کریمی (مدیریت تأمین تجهیزات)",
            "phone": "021-22334455",
            "email": "procurement@parspipeline.com",
            "address": "تهران، خیابان ولیعصر، برج پارس",
            "national_id": "10103214569",
            "credit_limit": 80000000000.0,
            "country_code": "IR"
        },
        {
            "name": "بازرگانی صنایع فلزی کاوه",
            "code": "CUST-003",
            "contact_person": "حاج‌آقا کاویانی (مدیر خرید بازار آهن شادآباد)",
            "phone": "021-66554433",
            "email": "kaveh_steel@gmail.com",
            "address": "تهران، بازار آهن شادآباد، بلوار طاووس، پلاک ۲۴",
            "national_id": "10100987654",
            "credit_limit": 30000000000.0,
            "country_code": "IR"
        },
        {
            "name": "مجتمع کشت و صنعت مغان",
            "code": "CUST-005",
            "contact_person": "مهندس باقری (تأمین نهاده‌های کشاورزی)",
            "phone": "045-32742000",
            "email": "agri@moghan.ir",
            "address": "اردبیل، دشت مغان، شرکت کشت و صنعت",
            "national_id": "10240055112",
            "credit_limit": 20000000000.0,
            "country_code": "IR"
        },
        {
            "name": "Rönesans Holding / İnşaat Sanayi ve Ticaret A.Ş.",
            "code": "TR-CUST-001",
            "contact_person": "Emre Şahin (Satın Alma ve Şantiye Tedarik Direktörü)",
            "phone": "03124413141",
            "email": "tedarik@ronesans.com",
            "address": "Çankaya, Ankara, Türkiye",
            "national_id": "7350021940",
            "vkn": "7350021940",
            "tax_office": "Başkent Vergi Dairesi",
            "mersis_no": "0735002194000019",
            "credit_limit": 15000000.0,
            "country_code": "TR"
        },
        {
            "name": "ENKA İnşaat ve Sanayi A.Ş.",
            "code": "TR-CUST-002",
            "contact_person": "Hakan Arslan (Endüstriyel Projeler Satın Alma)",
            "phone": "02123761000",
            "email": "procurement@enka.com",
            "address": "Balmumcu, Beşiktaş, İstanbul, Türkiye",
            "national_id": "3360018422",
            "vkn": "3360018422",
            "tax_office": "Beşiktaş Vergi Dairesi",
            "mersis_no": "0336001842200014",
            "credit_limit": 25000000.0,
            "country_code": "TR"
        },
        {
            "name": "Marmara Çelik Profil ve Dış Ticaret Ltd. Şti.",
            "code": "TR-CUST-003",
            "contact_person": "Ali Öztürk (Depo ve Dış Ticaret Müdürü)",
            "phone": "02164998877",
            "email": "info@marmaracelik.com.tr",
            "address": "Dudullu Organize Sanayi Bölgesi, Ümraniye, İstanbul",
            "national_id": "6120048192",
            "vkn": "6120048192",
            "tax_office": "Ümraniye Vergi Dairesi",
            "mersis_no": "0612004819200011",
            "credit_limit": 8000000.0,
            "country_code": "TR"
        }
    ]
    customers = {}
    for cust_info in customers_data:
        c = db.query(inventory_models.Customer).filter_by(code=cust_info["code"]).first()
        if not c:
            c = inventory_models.Customer(**cust_info)
            db.add(c)
            db.flush()
        customers[cust_info["code"]] = c
        customers[cust_info["name"]] = c
    print("✓ خریداران و پروژه‌های شاخص ایران و ترکیه آماده شدند.")

    # ----------------------------------------------------
    # ۵. تراکنش‌های انبار (حواله‌های ورود و خروج واقعی)
    # ----------------------------------------------------
    # انبار ۱: شمش و سنگین
    w_heavy = warehouses["انبار شماره یک (محوطه سنگین و شمش)"]
    # انبار ۲: مسقف و شیمیایی (اوره)
    w_chem = warehouses["انبار شماره دو (سوله مسقف و شیمیایی)"]
    # انبار ۳: روباز میلگرد و تیرآهن
    w_rebar = warehouses["انبار روباز تیرآهن و میلگرد"]

    # کاربر Admin جهت انتساب
    admin_user = db.query(auth_models.User).filter_by(username="admin").first()
    admin_id = admin_user.id if admin_user else None

    # بررسی وجود تراکنش‌ها
    tx_count = db.query(inventory_models.StockTransaction).count()
    if tx_count < 10:
        demo_transactions = [
            # ۱. ورود شمش فولادی ۱۵۰×۱۵۰ از فولاد خوزستان
            {
                "transaction_type": TransactionType.IN,
                "product": products["BLT-150-5SP-KSC"],
                "warehouse": w_heavy,
                "quantity": 25.0,  # ۲۵ تن
                "secondary_quantity": 12.0,  # ۱۲ قالب
                "secondary_uom": "قالب",
                "unit_price": 275000000.0,
                "batch_number": "BAT-2024-BLT-01",
                "heat_number": "HEAT-KSC-98421",
                "mtc_number": "MTC-2024-KSC-881",
                "chemical_analysis": "C:0.22%, Si:0.28%, Mn:1.45%, P:0.025%, S:0.022%",
                "mechanical_analysis": "Yield: 345 MPa, Tensile: 510 MPa, Elongation: 26%",
                "supplier": suppliers["SUP-004"],
                "waybill_number": "WB-IR-984401",
                "bill_of_lading_qty": 25.10,
                "shrinkage_qty": 0.10,
                "total_landed_cost": 6875000000.0,
                "status": DocumentStatus.APPROVED,
                "reference_document": "بارنامه شماره ۹۸۴۴۰۱ - ورودی محوطه شمش"
            },
            # ۲. ورود میلگرد سایز ۱۴ از ذوب‌آهن اصفهان
            {
                "transaction_type": TransactionType.IN,
                "product": products["REB-A3-14-ESCO"],
                "warehouse": w_rebar,
                "quantity": 24000.0,  # ۲۴ تن (۲۴,۰۰۰ کیلوگرم)
                "secondary_quantity": 1650.0,  # ۱,۶۵۰ شاخه
                "secondary_uom": "شاخه",
                "weight_per_unit": 14.54,
                "standard_weight": 14.52,
                "deviation_percent": 0.14,
                "unit_price": 285000.0,
                "batch_number": "BAT-2024-REB14-01",
                "heat_number": "HEAT-ESCO-78103",
                "mtc_number": "MTC-2024-ESCO-1402",
                "chemical_analysis": "C:0.32%, Si:0.55%, Mn:1.20%, P:0.030%, S:0.030%",
                "mechanical_analysis": "Yield: 420 MPa, Tensile: 620 MPa",
                "supplier": suppliers["SUP-002"],
                "waybill_number": "WB-IR-781031",
                "bill_of_lading_qty": 24000.0,
                "shrinkage_qty": 0.0,
                "total_landed_cost": 6840000000.0,
                "status": DocumentStatus.APPROVED,
                "reference_document": "حواله انبار ورودی بندیل‌های میلگرد ۱۴"
            },
            # ۳. ورود میلگرد سایز ۱۸ از ذوب‌آهن اصفهان
            {
                "transaction_type": TransactionType.IN,
                "product": products["REB-A3-18-ESCO"],
                "warehouse": w_rebar,
                "quantity": 22000.0,  # ۲۲ تن
                "secondary_quantity": 916.0,  # ۹۱۶ شاخه
                "secondary_uom": "شاخه",
                "weight_per_unit": 24.01,
                "standard_weight": 24.00,
                "unit_price": 290000.0,
                "batch_number": "BAT-2024-REB18-01",
                "heat_number": "HEAT-ESCO-78119",
                "mtc_number": "MTC-2024-ESCO-1409",
                "supplier": suppliers["SUP-002"],
                "waybill_number": "WB-IR-781190",
                "status": DocumentStatus.APPROVED,
                "reference_document": "رسید انبار میلگرد ۱۸ شاخه ۱۲ متری"
            },
            # ۴. ورود تیرآهن IPE 18 از ذوب‌آهن اصفهان
            {
                "transaction_type": TransactionType.IN,
                "product": products["BM-IPE-180-ESCO"],
                "warehouse": w_rebar,
                "quantity": 24800.0,  # ۲۴.۸ تن
                "secondary_quantity": 110.0,  # ۱۱۰ شاخه
                "secondary_uom": "شاخه",
                "weight_per_unit": 225.45,
                "standard_weight": 225.60,
                "unit_price": 315000.0,
                "batch_number": "BAT-2024-IPE18-01",
                "heat_number": "HEAT-ESCO-91102",
                "mtc_number": "MTC-2024-ESCO-IPE18",
                "supplier": suppliers["SUP-002"],
                "waybill_number": "WB-IR-911022",
                "status": DocumentStatus.APPROVED,
                "reference_document": "رسید انبار تیرآهن سنگین IPE 18"
            },
            # ۵. ورود اوره گرانول فله از پتروشیمی پردیس
            {
                "transaction_type": TransactionType.IN,
                "product": products["UREA-GRAN-PRD-46"],
                "warehouse": w_chem,
                "quantity": 50.0,  # ۵۰ تن
                "secondary_quantity": 50.0,
                "secondary_uom": "تن",
                "unit_price": 145000000.0,
                "batch_number": "BAT-2024-UREA-PRD",
                "heat_number": "CHEM-LOT-4412",
                "mtc_number": "COA-PRD-2024-991",
                "chemical_nitrogen": 46.3,
                "chemical_biuret": 0.82,
                "chemical_moisture": 0.22,
                "supplier": suppliers["SUP-003"],
                "waybill_number": "WB-IR-441209",
                "status": DocumentStatus.APPROVED,
                "reference_document": "رسید ورود اوره فله سوله شیمیایی"
            },
            # ۶. ورود شمش بیلت ۱۵۰×۱۵۰ از کارخانه کاردمیر ترکیه (TR-SUP-003)
            {
                "transaction_type": TransactionType.IN,
                "product": products["BLT-150-5SP-KSC"],
                "warehouse": w_heavy,
                "quantity": 26.0,  # ۲۶ تن
                "secondary_quantity": 13.0,
                "secondary_uom": "قالب",
                "unit_price": 310000000.0,
                "batch_number": "TR-BAT-KARDEMIR-150",
                "heat_number": "TR-HEAT-KRD-4019",
                "mtc_number": "TR-MTC-TS-EN-10025",
                "chemical_analysis": "C:0.18%, Mn:1.40%, Si:0.25%, P:0.020%, S:0.018%",
                "supplier": suppliers["TR-SUP-003"],
                "waybill_number": "TR-IRS-2024-00918",
                "status": DocumentStatus.APPROVED,
                "reference_document": "İthalat Giriş Fişi - Kardemir Kütük"
            },
            # ۷. خروج میلگرد سایز ۱۴ به پروژه برج آرمان امید (فروش / حواله خروج)
            {
                "transaction_type": TransactionType.OUT,
                "product": products["REB-A3-14-ESCO"],
                "warehouse": w_rebar,
                "quantity": 12000.0,  # ۱۲ تن
                "secondary_quantity": 825.0,  # ۸۲۵ شاخه
                "secondary_uom": "شاخه",
                "unit_price": 310000.0,
                "batch_number": "BAT-2024-REB14-01",
                "customer": customers["CUST-001"],
                "waybill_number": "INV-OUT-1403-101",
                "status": DocumentStatus.APPROVED,
                "reference_document": "حواله خروج میلگرد ۱۴ به کارگاه پروژه برج آرمان امید"
            },
            # ۸. خروج تیرآهن IPE 18 به شرکت توسعه خطوط لوله پارس (فروش)
            {
                "transaction_type": TransactionType.OUT,
                "product": products["BM-IPE-180-ESCO"],
                "warehouse": w_rebar,
                "quantity": 14880.0,  # ۶۶ شاخه
                "secondary_quantity": 66.0,
                "secondary_uom": "شاخه",
                "unit_price": 345000.0,
                "batch_number": "BAT-2024-IPE18-01",
                "customer": customers["CUST-002"],
                "waybill_number": "INV-OUT-1403-102",
                "status": DocumentStatus.APPROVED,
                "reference_document": "حواله خروج تیرآهن IPE 18 جهت پایپ رک خط لوله"
            },
            # ۹. خروج میلگرد ۱۸ به شرکت ساختمانی رونسانس ترکیه (TR-CUST-001)
            {
                "transaction_type": TransactionType.OUT,
                "product": products["REB-A3-18-ESCO"],
                "warehouse": w_rebar,
                "quantity": 15000.0,  # ۱۵ تن
                "secondary_quantity": 625.0,  # ۶۲۵ شاخه
                "secondary_uom": "شاخه",
                "unit_price": 330000.0,
                "batch_number": "BAT-2024-REB18-01",
                "customer": customers["TR-CUST-001"],
                "waybill_number": "TR-EXP-2024-5541",
                "status": DocumentStatus.APPROVED,
                "reference_document": "İhracat Çıkış İrsaliyesi - Rönesans Holding Ankara Projesi"
            },
            # ۱۰. خروج شمش فولادی ۱۵۰×۱۵۰ به بازرگانی صنایع فلزی کاوه (فروش)
            {
                "transaction_type": TransactionType.OUT,
                "product": products["BLT-150-5SP-KSC"],
                "warehouse": w_heavy,
                "quantity": 10.0,  # ۱۰ تن (۵ قالب)
                "secondary_quantity": 5.0,
                "secondary_uom": "قالب",
                "unit_price": 298000000.0,
                "batch_number": "BAT-2024-BLT-01",
                "customer": customers["CUST-003"],
                "waybill_number": "INV-OUT-1403-103",
                "status": DocumentStatus.APPROVED,
                "reference_document": "حواله خروج شمش فولادی به انبار شادآباد بازرگانی کاوه"
            }
        ]

        for tx_data in demo_transactions:
            prod = tx_data.pop("product")
            wh = tx_data.pop("warehouse")
            sup = tx_data.pop("supplier", None)
            cust = tx_data.pop("customer", None)
            tx = inventory_models.StockTransaction(
                product_id=prod.id,
                warehouse_id=wh.id,
                supplier_id=sup.id if sup else None,
                customer_id=cust.id if cust else None,
                created_by_id=admin_id,
                approved_by_id=admin_id,
                approved_at=datetime.now(),
                **tx_data
            )
            db.add(tx)
        db.commit()
        print("✓ حواله‌های ورود و خروج واقعی با شجره‌نامه ذوب و MTC ثبت گردیدند.")

    # ----------------------------------------------------
    # ۶. قبوض باسکول دیجیتال (Weighbridge Tickets)
    # ----------------------------------------------------
    wb_count = db.query(inventory_models.WeighbridgeTicket).count()
    if wb_count < 6:
        tickets_data = [
            # قبض ۱: ورود میلگرد ۱۴ با تریلی کفی ۱۸ چرخ (پلاک ایران)
            {
                "ticket_number": "WB-1403-1001",
                "truck_plate": "ایران ۶۸ - ۳۴۵ ع ۱۲",
                "driver_name": "محمد صادقی",
                "driver_phone": "09121112233",
                "truck_type": "تریلی کفی ۱۸ چرخ (بندیل و میلگرد)",
                "product": products["REB-A3-14-ESCO"],
                "warehouse": w_rebar,
                "supplier": suppliers["SUP-002"],
                "gross_weight": 38200.0,
                "tare_weight": 14200.0,
                "net_weight": 24000.0,
                "max_allowed_weight": 40000.0,
                "is_overweight": False,
                "status": WeighbridgeStatus.COMPLETED,
                "operator_name": "متصدی باسکول شیفت صبح (احمدی)",
                "notes": "ورودی میلگرد سایز ۱۴ ذوب‌آهن، توزین پر و خالی بدون مغایرت بارنامه",
                "completed_at": datetime.now() - timedelta(hours=3)
            },
            # قبض ۲: ورود تیرآهن IPE 18 با تریلی کفی (پلاک ایران)
            {
                "ticket_number": "WB-1403-1002",
                "truck_plate": "ایران ۲۲ - ۵۶۷ د ۳۴",
                "driver_name": "بهروز کریمی",
                "driver_phone": "09132224455",
                "truck_type": "تریلی کفی ۱۸ چرخ",
                "product": products["BM-IPE-180-ESCO"],
                "warehouse": w_rebar,
                "supplier": suppliers["SUP-002"],
                "gross_weight": 39000.0,
                "tare_weight": 14200.0,
                "net_weight": 24800.0,
                "max_allowed_weight": 40000.0,
                "is_overweight": False,
                "status": WeighbridgeStatus.COMPLETED,
                "operator_name": "متصدی باسکول شیفت صبح (احمدی)",
                "notes": "تیرآهن ۱۸ شاخه ۱۲ متری ذوب‌آهن اصفهان - تکمیل بارنامه",
                "completed_at": datetime.now() - timedelta(hours=2)
            },
            # قبض ۳: خروج میلگرد ۱۴ به مقصد برج آرمان امید (پلاک ایران)
            {
                "ticket_number": "WB-1403-1003",
                "truck_plate": "ایران ۱۱ - ۷۸۹ ب ۴۵",
                "driver_name": "علی اکبری",
                "driver_phone": "09124445566",
                "truck_type": "کامیون جفت (۱۰ چرخ)",
                "product": products["REB-A3-14-ESCO"],
                "warehouse": w_rebar,
                "customer": customers["CUST-001"],
                "gross_weight": 23500.0,
                "tare_weight": 11500.0,
                "net_weight": 12000.0,
                "max_allowed_weight": 26000.0,
                "is_overweight": False,
                "status": WeighbridgeStatus.COMPLETED,
                "operator_name": "متصدی باسکول شیفت عصر",
                "notes": "خروجی میلگرد ۱۴ به کارگاه برج آرمان امید",
                "completed_at": datetime.now() - timedelta(hours=1)
            },
            # قبض ۴: ورود شمش فولادی با تریلی استاندارد ترکیه (پلاک ترکیه ۳۴ استانبول)
            {
                "ticket_number": "WB-TR-2024-001",
                "truck_plate": "34 ABC 789",
                "driver_name": "Mehmet Demir",
                "driver_phone": "05321234567",
                "truck_type": "Standart 5 Dingilli Açık Kasa Treyler (Tır)",
                "product": products["BLT-150-5SP-KSC"],
                "warehouse": w_heavy,
                "supplier": suppliers["TR-SUP-003"],
                "gross_weight": 39400.0,
                "tare_weight": 14400.0,
                "net_weight": 25000.0,
                "max_allowed_weight": 40000.0,  # KGM 40t standard
                "is_overweight": False,
                "status": WeighbridgeStatus.COMPLETED,
                "operator_name": "Kantar Operatörü (Caner)",
                "notes": "Kardemir fabrika kütük sevkiyatı, KGM 40 ton yasal sınırına uygun tartım.",
                "completed_at": datetime.now() - timedelta(minutes=45)
            },
            # قبض ۵: خروج میلگرد ۱۸ برای هلدینگ ساختمانی رونسانس ترکیه (پلاک آنکارا ۰۶)
            {
                "ticket_number": "WB-TR-2024-002",
                "truck_plate": "06 TR 2024",
                "driver_name": "Emre Çelik",
                "driver_phone": "05423334455",
                "truck_type": "Tenteli / Kapalı Kasa Tır",
                "product": products["REB-A3-18-ESCO"],
                "warehouse": w_rebar,
                "customer": customers["TR-CUST-001"],
                "gross_weight": 38500.0,
                "tare_weight": 14200.0,
                "net_weight": 24300.0,
                "max_allowed_weight": 40000.0,
                "is_overweight": False,
                "status": WeighbridgeStatus.COMPLETED,
                "operator_name": "Kantar Operatörü (Caner)",
                "notes": "Rönesans Holding Ankara metro ve konut şantiyesi inşaat demiri sevkiyatı.",
                "completed_at": datetime.now() - timedelta(minutes=20)
            },
            # ۶. قبض باسکول در حال نوبت / توزین اول (پلاک ازمیر ۳۵)
            {
                "ticket_number": "WB-TR-2024-003",
                "truck_plate": "35 IZM 999",
                "driver_name": "Mustafa Yılmaz",
                "driver_phone": "05556667788",
                "truck_type": "Standart 5 Dingilli Açık Kasa Treyler (Tır)",
                "product": products["BM-IPE-180-ESCO"],
                "warehouse": w_rebar,
                "customer": customers["TR-CUST-002"],
                "gross_weight": 38750.0,
                "tare_weight": 0.0,
                "net_weight": 0.0,
                "max_allowed_weight": 40000.0,
                "is_overweight": False,
                "status": WeighbridgeStatus.FIRST_WEIGHING,
                "operator_name": "Kantar Operatörü (Caner)",
                "notes": "İlk tartım (Dolu ağırlık) alındı. Araç boşaltma sahasında bekliyor."
            }
        ]

        for wb_data in tickets_data:
            p = wb_data.pop("product")
            w = wb_data.pop("warehouse")
            s = wb_data.pop("supplier", None)
            c = wb_data.pop("customer", None)
            ticket = inventory_models.WeighbridgeTicket(
                product_id=p.id,
                warehouse_id=w.id,
                supplier_id=s.id if s else None,
                customer_id=c.id if c else None,
                **wb_data
            )
            db.add(ticket)
        db.commit()
        print("✓ قبوض باسکول هوشمند با پلاک‌های ایران و ترکیه و کنترل وزن KGM آماده شدند.")

    # ----------------------------------------------------
    # ۷. سفارشات خرید (Purchase Orders) با مالیات و توقیف مالیات آهن‌آلات (Tevkifat)
    # ----------------------------------------------------
    po_count = db.query(inventory_models.PurchaseOrder).count()
    if po_count < 3:
        # ۱. سفارش خرید از ذوب‌آهن اصفهان (IRR)
        po1 = inventory_models.PurchaseOrder(
            po_number="PO-1403-ESCO-01",
            supplier_id=suppliers["SUP-002"].id,
            delivery_due_date="۱۴۰۳/۰۹/۱۵",
            status=PurchaseOrderStatus.CONFIRMED,
            subtotal_amount=15000000000.0,
            vat_rate=0.10,
            vat_amount=1500000000.0,
            total_amount=16500000000.0,
            currency="IRR",
            notes="قرارداد خرید میلگرد ۱۴ و ۱۸ شاخه‌ای ذوب‌آهن تحویل انبار مرکزی"
        )
        db.add(po1)
        db.flush()
        db.add_all([
            inventory_models.PurchaseOrderItem(
                purchase_order_id=po1.id,
                product_id=products["REB-A3-14-ESCO"].id,
                quantity=30000.0,
                received_quantity=24000.0,
                unit_price=285000.0,
                total_price=8550000000.0
            ),
            inventory_models.PurchaseOrderItem(
                purchase_order_id=po1.id,
                product_id=products["REB-A3-18-ESCO"].id,
                quantity=22000.0,
                received_quantity=22000.0,
                unit_price=290000.0,
                total_price=6380000000.0
            )
        ])

        # ۲. سفارش خرید ترکیه از کاردمیر با نسبت توقیف قانونی آهن‌آلات 4/10 (TRY)
        po_tr = inventory_models.PurchaseOrder(
            po_number="TR-PO-2024-KRD-01",
            supplier_id=suppliers["TR-SUP-003"].id,
            delivery_due_date="2024-11-20",
            status=PurchaseOrderStatus.CONFIRMED,
            subtotal_amount=1200000.0,  # ۱,۲۰۰,۰۰۰ لیر
            vat_rate=0.20,             # ۲۰٪ KDV
            vat_amount=240000.0,        # کل مالیات
            tevkifat_rate="4/10",       # نسبت توقیف ۴/۱۰ آهن‌آلات و شمش طبق بخشنامه مالیاتی ترکیه
            tevkifat_amount=96000.0,    # توقیف توسط خریدار
            total_amount=1344000.0,     # مبلغ قابل پرداخت به فروشنده
            currency="TRY",
            notes="Kardemir S235JR kare kütük alım sözleşmesi, %20 KDV ve 4/10 demir tevkifatlı."
        )
        db.add(po_tr)
        db.flush()
        db.add(inventory_models.PurchaseOrderItem(
            purchase_order_id=po_tr.id,
            product_id=products["BLT-150-5SP-KSC"].id,
            quantity=60.0,
            received_quantity=26.0,
            unit_price=20000.0,
            total_price=1200000.0
        ))
        db.commit()
        print("✓ سفارشات خرید با رعایت استانداردهای مالیاتی و توقیف Tevkifat ترکیه آماده شدند.")

    # ----------------------------------------------------
    # ۸. دستورات برش آهن‌آلات و مدیریت ته‌شاخه (Cutting Orders)
    # ----------------------------------------------------
    cut_count = db.query(inventory_models.CuttingOrder).count()
    if cut_count < 2:
        db.add_all([
            inventory_models.CuttingOrder(
                order_number="CUT-1403-101",
                product_id=products["REB-A3-14-ESCO"].id,
                original_length=12.0,
                cut_length=4.5,
                pieces_count=2,
                remnant_length=3.0,
                remnant_weight=43.56,
                destination="انبار ته‌شاخه‌ها",
                status=CuttingStatus.COMPLETED,
                notes="برش شاخه ۱۲ متری میلگرد ۱۴ به ۲ قطعه ۴.۵ متری برای ستون، باقیمانده ۳ متر ته‌شاخه سالم"
            ),
            inventory_models.CuttingOrder(
                order_number="CUT-1403-102",
                product_id=products["BM-IPE-180-ESCO"].id,
                original_length=12.0,
                cut_length=5.8,
                pieces_count=2,
                remnant_length=0.4,
                remnant_weight=90.24,
                destination="انبار ته‌شاخه‌ها",
                status=CuttingStatus.COMPLETED,
                notes="برش شاخه تیرآهن ۱۸ برای تیر ریزی، پرتی ۴۰ سانتی‌متر"
            )
        ])
        db.commit()
        print("✓ دستورات برش و مدیریت ته‌شاخه‌ها آماده شدند.")

    # ----------------------------------------------------
    # ۹. دستور کیسه‌گیری فله به جامبوبگ اوره (Bagging Orders)
    # ----------------------------------------------------
    bag_count = db.query(inventory_models.BaggingOrder).count()
    if bag_count < 1:
        prod_bulk = products["UREA-GRAN-PRD-46"]
        prod_bag = products["UREA-BAG-1T-PRD"]
        db.add(inventory_models.BaggingOrder(
            order_number="BAG-1403-001",
            bulk_product_id=prod_bulk.id,
            packaged_product_id=prod_bag.id,
            bulk_tonnage_used=50.0,
            packages_produced=50.0,
            package_type="جامبوبگ ۱ تنی",
            waste_tonnage=0.15,
            packaging_cost_per_ton=450000.0,
            status=BaggingStatus.COMPLETED,
            notes="عملیات کیسه‌گیری پارت صادراتی اوره فله به کیسه‌های ۱ تنی مقاوم جهت حمل دریایی"
        ))
        db.commit()
        print("✓ دستور کیسه‌گیری فله اوره به جامبوبگ آماده شد.")

    print("=" * 60)
    print("✅ کلیه داده‌های نمونه، محصولات، تراکنش‌ها، باسکول و طرف‌های تجاری با موفقیت تزریق شدند!")
    print("=" * 60)


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
