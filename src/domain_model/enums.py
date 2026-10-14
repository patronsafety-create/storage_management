from enum import Enum

class DocumentType(str, Enum):
    RECEIPT = "RECEIPT"  # رسید انبار (ورودی کالا)
    ISSUE = "ISSUE"      # حواله انبار (خروجی کالا)

class DocumentStatus(str, Enum):
    DRAFT = "DRAFT"                            # پیش‌نویس (توسط اپراتور انبار)
    PENDING_APPROVAL = "PENDING_APPROVAL"      # در انتظار تایید سرپرست/مدیر
    PENDING_MANAGER = "PENDING_MANAGER"        # سازگاری با تعاریف قبلی
    PENDING_ACCOUNTING = "PENDING_ACCOUNTING"  # در انتظار تایید حسابداری
    APPROVED = "APPROVED"                      # تایید نهایی و اثرگذاری در کاردکس و موجودی
    REJECTED = "REJECTED"                      # رد شده با درج علت
    CANCELLED = "CANCELLED"                    # باطل شده

class PurchaseOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class WeighbridgeStatus(str, Enum):
    FIRST_WEIGHING = "FIRST_WEIGHING"  # توزین اول (خالی یا پر)
    COMPLETED = "COMPLETED"            # توزین دوم انجام شده و قطعی
    CANCELLED = "CANCELLED"            # باطل شده

class CuttingStatus(str, Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class BaggingStatus(str, Enum):
    DRAFT = "DRAFT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class SalesOrderStatus(str, Enum):
    DRAFT = "DRAFT"
    CONFIRMED = "CONFIRMED"
    PARTIALLY_DELIVERED = "PARTIALLY_DELIVERED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class TransactionSource(str, Enum):
    OPENING_BALANCE = "OPENING_BALANCE"      # موجودی اول دوره
    PURCHASE = "PURCHASE"                    # رسید خرید (PO)
    SALES = "SALES"                          # حواله فروش (SO)
    IN_ADJUSTMENT = "IN_ADJUSTMENT"          # اصلاحیه ورودی
    OUT_ADJUSTMENT = "OUT_ADJUSTMENT"        # اصلاحیه خروجی
    PRICE_ADJUSTMENT = "PRICE_ADJUSTMENT"    # اصلاحیه ریالی / بهای تمام‌شده
    TRANSFER = "TRANSFER"                    # انتقال بین انبارها
    BAGGING = "BAGGING"                      # کیسه‌گیری
    CUTTING = "CUTTING"                      # برش آهن‌آلات
    STOCKTAKING = "STOCKTAKING"              # انبارگردانی
    RETURN = "RETURN"                        # مرجوعی
    INTERNAL_USE = "INTERNAL_USE"            # مصرف داخلی
