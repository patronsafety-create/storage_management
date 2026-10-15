"""
ماژول نرم‌سازی هوشمند اعداد، ارقام و ممیزهای دو زبانه (ایران و ترکیه)
NexusPour ERP - Enterprise Number Normalizer
طراحی شده جهت سازگاری کامل با کیبورد فارسی، عربی و استانداردهای اعشاری ترکیه (Turkish Decimal Comma).
حقوق مالکیت معنوی: امید پورمحمود (Omid Pourmahmoud)
"""
import re
import urllib.parse
from typing import Any, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ENGLISH_DIGITS = "0123456789"

_DIGIT_MAP = str.maketrans(
    PERSIAN_DIGITS + ARABIC_DIGITS,
    ENGLISH_DIGITS + ENGLISH_DIGITS
)


def to_english_digits(val: Optional[str]) -> str:
    """تبدیل تمام ارقام فارسی و عربی به ارقام انگلیسی 0-9"""
    if val is None:
        return ""
    s = str(val)
    return s.translate(_DIGIT_MAP)


def normalize_number_str(val: Optional[str], treat_comma_as_decimal: bool = True) -> str:
    """
    نرمال‌سازی هوشمند رشته‌های عددی:
    1. تبدیل ارقام فارسی و عربی به انگلیسی
    2. تبدیل نماد ممیز عربی (٫) به نقطه
    3. تبدیل ویرگول اعشار ترکیبی/ترکی (مانند 24,5) به نقطه (24.5)
    4. حذف جداکننده‌های هزارگان در هر دو فرمت انگلیسی (1,250.50) و ترکی (1.250,50)
    """
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return ""

    # ۱. تبدیل ارقام
    s = s.translate(_DIGIT_MAP)
    # ۲. تبدیل ممیز عربی
    s = s.replace("\u066b", ".")
    # حذف فاصله‌های خالی بین اعداد
    s = s.replace(" ", "")

    # ۳. مدیریت ویرگول و نقطه
    if "," in s and "." in s:
        # هر دو وجود دارند: بررسی اینکه کدام در آخر است (اعشار در آخر قرار می‌گیرد)
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma > last_dot:
            # فرمت رسمی ترکی و اروپایی: 1.250,50 -> 1250.50
            s = s.replace(".", "").replace(",", ".")
        else:
            # فرمت انگلیسی: 1,250.50 -> 1250.50
            s = s.replace(",", "")
    elif "," in s:
        # فقط ویرگول وجود دارد
        if treat_comma_as_decimal:
            # در ورودی‌های انبار/وزن/تعداد، "24,5" به معنی "24.5" است
            s = s.replace(",", ".")

    return s


def parse_float_safe(val: Any, default: float = 0.0) -> float:
    """
    پارس امن اعشاری با قابلیت پذیرش اعداد فارسی، عربی و ممیز ترکی
    """
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)

    s = normalize_number_str(str(val))
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def parse_int_safe(val: Any, default: int = 0) -> int:
    """پارس امن عدد صحیح با پشتیبانی از ارقام فارسی و عربی"""
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)

    s = to_english_digits(str(val)).strip()
    s = re.sub(r"[^\d\-]", "", s)
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


# کلمات کلیدی فیلدهای عددی فرم‌ها که در صورت وجود ویرگول باید به نقطه اعشار تبدیل شوند
NUMERIC_FIELD_KEYWORDS = {
    "qty", "quantity", "price", "unit_price", "weight", "gross", "tare", "net",
    "cost", "freight", "insurance", "weighbridge", "tolerance", "penalty",
    "amount", "subtotal", "vat", "tevkifat", "total", "credit", "limit",
    "length", "thickness", "nominal", "min_stock", "max_stock", "reorder",
    "secondary_quantity", "rate", "exchange_rate", "diff", "count"
}


def is_numeric_field_name(field_name: str) -> bool:
    """تشخیص نام فیلدهایی که ماهیت عددی یا اعشاری دارند"""
    fn = field_name.lower()
    if fn.startswith("count_") or fn.startswith("sec_count_"):
        return True
    return any(kw in fn for kw in NUMERIC_FIELD_KEYWORDS)


def normalize_form_urlencoded_body(body_bytes: bytes) -> bytes:
    """
    نرمال‌سازی کل بادی فرم‌های x-www-form-urlencoded قبل از تحویل به Pydantic و FastAPI
    """
    if not body_bytes:
        return body_bytes

    try:
        decoded_str = body_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return body_bytes

    # پارس پارامترها با حفظ ترتیب
    pairs = urllib.parse.parse_qsl(decoded_str, keep_blank_values=True)
    new_pairs = []

    for key, val in pairs:
        # اگر فیلد خالی است
        if not val or val.strip() == "":
            # برای فیلدهای عددی، شناسه‌ها یا هزینه‌ها، ارسال کلید با مقدار خالی "" باعث کرش ۴۲۲ در Pydantic می‌شود.
            # با حذف این کلید از بادی، فاست‌ای‌پی به صورت خودکار مقدار پیش‌فرض Form(None) یا Form(0.0) را اعمال می‌کند.
            if is_numeric_field_name(key) or key.endswith("_id") or key in ("secondary_quantity", "unit_price", "quantity", "exchange_rate"):
                continue
            new_pairs.append((key, ""))
            continue

        # در تمامی فیلدها، ارقام فارسی و عربی را به انگلیسی تبدیل می‌کنیم (مانند تلفن، کد ملی، شماره بارنامه و ...)
        converted_val = to_english_digits(val)

        # در فیلدهای عددی، ویرگول‌های اعشاری (فرمت ترکی) را نیز به نقطه تبدیل می‌کنیم
        if is_numeric_field_name(key) or re.search(r"^\s*[\+\-]?\d+,\d+\s*$", converted_val):
            converted_val = normalize_number_str(converted_val)

        new_pairs.append((key, converted_val))

    new_encoded = urllib.parse.urlencode(new_pairs)
    return new_encoded.encode("utf-8")


class NumberNormalizationMiddleware(BaseHTTPMiddleware):
    """
    Middleware سراسری برای یکپارچه‌سازی و نرمال‌سازی اعداد در سطح درخواست‌های HTTP:
    جلوگیری قطعی از کرش کردن فرم‌ها به خاطر ارقام فارسی/عربی کیبورد یا ویرگول اعشار ترکی.
    """
    async def dispatch(self, request: Request, call_next):
        content_type = request.headers.get("content-type", "")

        # فقط فرم‌های استاندارد urlencoded را بازنویسی می‌کنیم
        if "application/x-www-form-urlencoded" in content_type and request.method in ("POST", "PUT", "PATCH"):
            raw_body = await request.body()
            if raw_body:
                normalized_body = normalize_form_urlencoded_body(raw_body)
                request._body = normalized_body

                async def receive():
                    return {"type": "http.request", "body": normalized_body, "more_body": False}

                request._receive = receive

        return await call_next(request)
