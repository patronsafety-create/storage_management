from enum import Enum

class DocumentType(str, Enum):
    RECEIPT = "RECEIPT"  # رسید انبار (ورودی کالا)
    ISSUE = "ISSUE"      # حواله انبار (خروجی کالا)

class DocumentStatus(str, Enum):
    DRAFT = "DRAFT"                            # پیش‌نویس (توسط اپراتور انبار)
    PENDING_MANAGER = "PENDING_MANAGER"        # در انتظار تایید مدیر انبار
    PENDING_ACCOUNTING = "PENDING_ACCOUNTING"  # در انتظار تایید حسابداری
    APPROVED = "APPROVED"                      # تایید نهایی و اثرگذاری در موجودی
    REJECTED = "REJECTED"                      # رد شده توسط مدیر یا حسابدار