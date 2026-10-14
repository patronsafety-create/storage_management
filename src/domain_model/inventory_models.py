"""
مدل‌های موجودی انبار
این فایل تنها منبع حقیقت برای جداول products، warehouses و stock_transactions است.
"""
import enum
from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey, CheckConstraint, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.infrastructure.database import Base
from src.domain_model.auth_models import User


from src.domain_model.enums import (
    DocumentStatus,
    PurchaseOrderStatus,
    WeighbridgeStatus,
    CuttingStatus,
    BaggingStatus
)


class TransactionType(str, enum.Enum):
    IN = "IN"
    OUT = "OUT"


class ProductCategory(Base):
    """دسته‌بندی درختی و سلسله‌مراتبی کالاها"""
    __tablename__ = "product_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, nullable=True, unique=True)  # کد رده کالا مثلاً STL-REB
    description = Column(String, nullable=True)
    parent_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)

    parent = relationship("ProductCategory", remote_side=[id], backref="children")
    products = relationship("Product", back_populates="category")


class Product(Base):
    """کالاهای قابل نگهداری در انبار"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    uom = Column(String, nullable=False, default="عدد")  # واحد سنجش اصلی (مثلاً کیلوگرم یا تن)
    secondary_uom = Column(String, nullable=True)        # واحد سنجش فرعی (مثلاً شاخه، بندیل، قالب، کیسه)
    nominal_weight = Column(Float, nullable=True, default=0.0) # وزن نامی استاندارد هر شاخه/بسته به کیلوگرم
    sku = Column(String, unique=True, index=True, nullable=True)  # شناسه یا بارکد یکتا
    irc_code = Column(String, nullable=True)             # شناسه کالا در سامانه جامع تجارت (IRC)
    hs_code = Column(String, nullable=True)              # کد تعرفه گمرکی بین‌المللی (HS Code)
    gtip_code = Column(String, nullable=True)            # کد ۱۲ رقمی تعرفه گمرکی ترکیه (GTİP - Gümrük Tarife İstatistik Pozisyonu)
    tse_standard = Column(String, nullable=True)         # استاندارد ملی ترکیه (TSE - Türk Standardları Enstitüsü مانند TS 708)
    category_id = Column(Integer, ForeignKey("product_categories.id"), nullable=True)

    # 🔬 مشخصات صنعتی و متالورژی
    brand = Column(String, nullable=True)       # کارخانه یا برند سازنده (مانند ذوب‌آهن، مبارکه، نیشابور، پتروشیمی)
    size = Column(String, nullable=True)        # سایز ابعادی (مثلاً ۱۶، ۱۸، IPE 20، ضخامت ۲ میل)
    length = Column(Float, nullable=True)       # طول استاندارد شاخه به متر (مثلاً ۱۲ یا ۶)
    thickness = Column(Float, nullable=True)    # ضخامت به میلی‌متر
    grade = Column(String, nullable=True)       # گرید آلیاژی (A3, A2, 3SP, 5SP, Gr46)
    standard = Column(String, nullable=True)    # استاندارد تولید (DIN 488, ISIRI 3132, ASTM)

    # 📦 پارامترهای کنترل انبارداری و هشدار
    min_stock = Column(Float, nullable=True, default=0.0)      # حداقل موجودی امن
    max_stock = Column(Float, nullable=True, default=0.0)      # سقف انبارداری
    reorder_point = Column(Float, nullable=True, default=0.0)  # نقطه سفارش مجدد
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("ProductCategory", back_populates="products")
    transactions = relationship("StockTransaction", back_populates="product")


class Warehouse(Base):
    """انبارهای سازمان"""
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)

    transactions = relationship("StockTransaction", back_populates="warehouse")


class Supplier(Base):
    """تأمین‌کنندگان کالا و کارخانجات تولیدی"""
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, unique=True, nullable=True)  # کد تأمین‌کننده مثلاً SUP-001
    contact_person = Column(String, nullable=True)     # شخص رابط
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    national_id = Column(String, nullable=True)        # شناسه ملی / کد اقتصادی
    vkn = Column(String, nullable=True)                # شناسه مالیاتی ترکیه (VKN / T.C. Kimlik)
    tax_office = Column(String, nullable=True)         # حوزه مالیاتی ترکیه (Vergi Dairesi)
    mersis_no = Column(String, nullable=True)          # شماره مرسیس ترکیه (MERSİS No)
    country_code = Column(String, default="IR")        # کد کشور (IR یا TR)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("StockTransaction", back_populates="supplier")


class Customer(Base):
    """مشتریان، خریداران و پیمانکاران پروژه"""
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, unique=True, nullable=True)  # کد مشتری مثلاً CUST-001
    contact_person = Column(String, nullable=True)     # شخص رابط
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    address = Column(String, nullable=True)
    national_id = Column(String, nullable=True)        # شناسه ملی / کد اقتصادی
    vkn = Column(String, nullable=True)                # شناسه مالیاتی ترکیه (VKN / T.C. Kimlik)
    tax_office = Column(String, nullable=True)         # حوزه مالیاتی ترکیه (Vergi Dairesi)
    mersis_no = Column(String, nullable=True)          # شماره مرسیس ترکیه (MERSİS No)
    country_code = Column(String, default="IR")        # کد کشور (IR یا TR)
    credit_limit = Column(Float, default=0.0)          # سقف اعتبار ریالی / ارزی
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    transactions = relationship("StockTransaction", back_populates="customer")


class StockTransaction(Base):
    """سند رسید یا حواله انبار با پشتیبانی از گردش تأیید و محاسبات صنعتی"""
    __tablename__ = "stock_transactions"

    id = Column(Integer, primary_key=True, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    batch_number = Column(String, nullable=True)
    reference_document = Column(String, nullable=True)
    unit_price = Column(Float, nullable=True, default=0.0)  # قیمت واحد برای کاردکس ریالی
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 🌟 گردش کار و وضعیت تایید سند (Package 0-C)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.APPROVED, nullable=False)
    rejection_reason = Column(String, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    # 🔄 برگشت از خرید / فروش (Package 3)
    is_return = Column(Boolean, default=False)
    return_reason = Column(String, nullable=True)
    parent_transaction_id = Column(Integer, ForeignKey("stock_transactions.id"), nullable=True)

    # ⚖️ موتور دو واحدی دینامیک - شاخه ⇄ کیلوگرم (Package 4)
    secondary_quantity = Column(Float, nullable=True)  # تعداد شاخه / بندیل / کیسه
    secondary_uom = Column(String, nullable=True)      # شاخه، بندیل، قالب، کیسه
    weight_per_unit = Column(Float, nullable=True)     # میانگین وزن هر شاخه
    standard_weight = Column(Float, nullable=True)     # وزن استاندارد اشتال
    deviation_percent = Column(Float, nullable=True)   # درصد انحراف خط نورد

    # 🚚 بهای تمام‌شده تجمیعی و تلورانس بارنامه (Package 6)
    freight_cost = Column(Float, default=0.0)          # کرایه حمل بارنامه
    insurance_cost = Column(Float, default=0.0)        # حق بیمه حمل
    weighbridge_cost = Column(Float, default=0.0)      # هزینه باسکول
    bill_of_lading_qty = Column(Float, nullable=True)  # وزن مبدا در بارنامه
    shrinkage_qty = Column(Float, nullable=True)       # مقدار کسری/افت مسیر
    shrinkage_percent = Column(Float, nullable=True)   # درصد افت بار
    allowed_tolerance_percent = Column(Float, default=0.3) # تلورانس مجاز
    penalty_amount = Column(Float, default=0.0)        # جریمه راننده/باربری
    total_landed_cost = Column(Float, default=0.0)     # بهای تمام‌شده تجمیعی

    # 🔬 شجره‌نامه ذوب و شناسنامه متالورژی MTC (Package 9)
    heat_number = Column(String, nullable=True)        # شماره ذوب کوره
    mtc_number = Column(String, nullable=True)         # شماره گواهینامه آزمایشگاه
    chemical_analysis = Column(String, nullable=True)  # آنالیز شیمیایی C, Si, Mn, P, S
    mechanical_analysis = Column(String, nullable=True)# تست مکانیکی کشش و تسلیم
    chemical_nitrogen = Column(Float, nullable=True)   # درصد ازت اوره (۴۶٪)
    chemical_biuret = Column(Float, nullable=True)     # درصد بیورت اوره
    chemical_moisture = Column(Float, nullable=True)   # درصد رطوبت اوره

    # 🏛️ سامانه جامع تجارت و بارنامه (Package 12)
    waybill_number = Column(String, nullable=True)     # شماره بارنامه برخط
    tracking_code = Column(String, nullable=True)      # کد رهگیری جامع تجارت

    # 🌟 ردیابی ثبت‌کننده سند
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # 🤝 اتصال به طرف‌های تجاری
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    product = relationship("Product", back_populates="transactions")
    warehouse = relationship("Warehouse", back_populates="transactions")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    supplier = relationship("Supplier", back_populates="transactions")
    customer = relationship("Customer", back_populates="transactions")
    parent_transaction = relationship("StockTransaction", remote_side=[id], backref="return_transactions")

    __table_args__ = (
        CheckConstraint('quantity > 0', name='check_quantity_positive'),
    )


# ========================================================
# 📦 فاز ۱: سفارش خرید (Purchase Orders)
# ========================================================

class PurchaseOrder(Base):
    """سفارش خرید کالا از تأمین‌کننده"""
    __tablename__ = "purchase_orders"

    id = Column(Integer, primary_key=True, index=True)
    po_number = Column(String, unique=True, nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    order_date = Column(DateTime(timezone=True), server_default=func.now())
    delivery_due_date = Column(String, nullable=True)
    status = Column(Enum(PurchaseOrderStatus), default=PurchaseOrderStatus.CONFIRMED, nullable=False)
    notes = Column(String, nullable=True)

    # 💰 اطلاعات مالی و مالیاتی (Tax & Tevkifat)
    subtotal_amount = Column(Float, default=0.0)      # مبلغ پایه بدون مالیات (Matrah)
    vat_rate = Column(Float, default=0.10)            # نرخ مالیات بر ارزش افزوده (۱۰٪ ایران یا ۲۰٪ ترکیه)
    vat_amount = Column(Float, default=0.0)           # کل مالیات بر ارزش افزوده (Hesaplanan KDV)
    tevkifat_rate = Column(String, nullable=True)     # نسبت توقیف مالیات آهن‌آلات ترکیه (مانند 4/10)
    tevkifat_amount = Column(Float, default=0.0)      # مبلغ توقیف مالیات (Tevkifat Tutarı)
    total_amount = Column(Float, default=0.0)         # کل مبلغ قابل پرداخت به فروشنده (Genel Toplam)
    currency = Column(String, default="IRR")          # واحد پولی (IRR یا TRY)

    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    supplier = relationship("Supplier", backref="purchase_orders")
    created_by = relationship("User", foreign_keys=[created_by_id])
    items = relationship("PurchaseOrderItem", back_populates="purchase_order", cascade="all, delete-orphan")


class PurchaseOrderItem(Base):
    """اقلام سفارش خرید"""
    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Float, nullable=False)
    received_quantity = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    total_price = Column(Float, default=0.0)

    purchase_order = relationship("PurchaseOrder", back_populates="items")
    product = relationship("Product")


# ========================================================
# 🚛 فاز ۲: باسکول تریلی (Weighbridge Tickets)
# ========================================================

class WeighbridgeTicket(Base):
    """قبض و نوبت باسکول تریلی و ناوگان حمل و نقل"""
    __tablename__ = "weighbridge_tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_number = Column(String, unique=True, nullable=False, index=True)
    truck_plate = Column(String, nullable=False)
    driver_name = Column(String, nullable=False)
    driver_phone = Column(String, nullable=True)
    truck_type = Column(String, default="تریلی کفی ۱۸ چرخ")
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False)
    
    gross_weight = Column(Float, nullable=True, default=0.0)               # وزن ناخالص (پر) به کیلوگرم
    tare_weight = Column(Float, nullable=True, default=0.0)                # وزن خالی (تار) به کیلوگرم
    net_weight = Column(Float, nullable=True, default=0.0)                 # وزن خالص به کیلوگرم
    max_allowed_weight = Column(Float, default=40000.0)                    # حداکثر وزن مجاز ناخالص (کیلوگرم)
    is_overweight = Column(Boolean, default=False)                         # هشدار اضافه تناژ
    
    status = Column(Enum(WeighbridgeStatus), default=WeighbridgeStatus.FIRST_WEIGHING)
    notes = Column(String, nullable=True)
    operator_name = Column(String, nullable=True)
    stock_transaction_id = Column(Integer, ForeignKey("stock_transactions.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    supplier = relationship("Supplier")
    customer = relationship("Customer")
    product = relationship("Product")
    warehouse = relationship("Warehouse")
    stock_transaction = relationship("StockTransaction")


# ========================================================
# ✂️ فاز ۲: دستور برش آهن‌آلات و مدیریت ته‌شاخه (Cutting Orders)
# ========================================================

class CuttingOrder(Base):
    """دستور برش آهن‌آلات و مدیریت ته‌شاخه و پرتی"""
    __tablename__ = "cutting_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    original_length = Column(Float, default=12.0)  # طول شاخه مادر به متر
    cut_length = Column(Float, nullable=False)      # طول قطعه برش خورده تحویلی به متر
    pieces_count = Column(Integer, default=1)       # تعداد قطعات برش
    remnant_length = Column(Float, nullable=False)  # طول باقیمانده ته‌شاخه به متر
    remnant_weight = Column(Float, default=0.0)     # وزن تقریبی ته‌شاخه به کیلوگرم
    destination = Column(String, default="انبار ته‌شاخه‌ها") # یا انبار ضایعات آهن
    status = Column(Enum(CuttingStatus), default=CuttingStatus.COMPLETED)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product")


# ========================================================
# 🌾 فاز ۲: کیسه‌گیری فله به جامبوبگ اوره (Bagging Orders)
# ========================================================

class BaggingOrder(Base):
    """دستور کیسه‌گیری فله به جامبوبگ یا کیسه اوره"""
    __tablename__ = "bagging_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String, unique=True, nullable=False, index=True)
    bulk_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    packaged_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    bulk_tonnage_used = Column(Float, nullable=False)       # تناژ فله مصرفی (تن)
    packages_produced = Column(Float, nullable=False)       # تعداد کیسه/جامبوبگ تولیدی
    package_type = Column(String, default="جامبوبگ ۱ تنی")   # نوع بسته‌بندی
    waste_tonnage = Column(Float, default=0.0)              # ریزش و پرتی (تن)
    packaging_cost_per_ton = Column(Float, default=0.0)     # هزینه دستمزد و بسته‌بندی هر تن
    status = Column(Enum(BaggingStatus), default=BaggingStatus.COMPLETED)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    bulk_product = relationship("Product", foreign_keys=[bulk_product_id])
    packaged_product = relationship("Product", foreign_keys=[packaged_product_id])


# ========================================================
# 🛡️ فاز ۳: لاگ جامع حسابرسی و ردپای امنیتی (Audit Logs)
# ========================================================

class AuditLog(Base):
    """لاگ جامع حسابرسی رویدادها و ردپای امنیتی"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    user_name = Column(String, nullable=True)
    action = Column(String, nullable=False) # CREATE, UPDATE, APPROVE, REJECT, CANCEL, DELETE
    entity_name = Column(String, nullable=False) # StockTransaction, Product, PurchaseOrder, WeighbridgeTicket
    entity_id = Column(String, nullable=True)
    details = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")