import re
from typing import Optional, Tuple

def validate_vkn(vkn: str) -> bool:
    """
    اعتبارسنجی ریاضی رسمی شناسه مالیاتی ۱۰ رقمی شرکت‌های ترکیه (Vergi Kimlik Numarası - VKN)
    مطابق الگوریتم رسمی اداره درآمدهای مالیاتی ترکیه (GİB)
    """
    if not vkn:
        return False
    clean = str(vkn).strip().replace(" ", "").replace("-", "")
    if len(clean) != 10 or not clean.isdigit():
        return False

    s = 0
    for i, n in enumerate(reversed(clean[:9]), 1):
        c1 = (int(n) + i) % 10
        if c1:
            c2 = (c1 * (2 ** i)) % 9 or 9
            s += c2
    check_digit = str((10 - s) % 10)
    return clean[9] == check_digit


def validate_tc_kimlik(tc: str) -> bool:
    """
    اعتبارسنجی الگوریتم رسمی ۱۱ رقمی کد ملی اشخاص حقیقی ترکیه (T.C. Kimlik Numarası)
    مطابق با الگوریتم سازمان ثبت احوال ترکیه (Nüfus ve Vatandaşlık İşleri)
    """
    if not tc:
        return False
    clean = str(tc).strip().replace(" ", "").replace("-", "")
    if len(clean) != 11 or not clean.isdigit() or clean[0] == '0':
        return False

    d = [int(c) for c in clean]
    odd_sum = d[0] + d[2] + d[4] + d[6] + d[8]
    even_sum = d[1] + d[3] + d[5] + d[7]

    digit_10 = ((7 * odd_sum) - even_sum) % 10
    if d[9] != digit_10:
        return False

    digit_11 = sum(d[:10]) % 10
    return d[10] == digit_11


def validate_turkish_phone(phone: str) -> bool:
    """
    اعتبارسنجی شماره تلفن و همراه در ترکیه:
    ۱۰ رقم بدون صفر (مثل 5321234567) یا ۱۱ رقم با صفر (مثل 05321234567 یا خط ثابت 02121234567)
    یا با پیش‌شماره بین‌المللی +90
    """
    if not phone:
        return False
    clean = str(phone).strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if clean.startswith("+90"):
        clean = "0" + clean[3:]
    elif clean.startswith("90") and len(clean) == 12:
        clean = "0" + clean[2:]

    if len(clean) == 10 and not clean.startswith("0"):
        clean = "0" + clean

    if len(clean) == 11 and clean.isdigit() and clean.startswith("0"):
        # پیش‌شماره معتبر ترکیه (05xx موبایل یا کدهای استانی 02xx, 03xx, 04xx)
        return clean[1] in ("2", "3", "4", "5")
    return False


def validate_turkish_party_data(
    name: str,
    phone: Optional[str],
    national_id: Optional[str],
    party_type_label: str = "Cari Hesap"
) -> Tuple[Optional[str], str, Optional[str], Optional[str]]:
    """
    اعتبارسنجی جامع مشخصات طرف تجاری بر اساس قوانین کشور ترکیه:
    1. نام شرکت یا شخص: حداقل ۳ کاراکتر
    2. شماره تماس ترکیه: معتبر با پیش‌شماره استاندارد
    3. شناسه مالیاتی: VKN ده رقمی یا T.C. Kimlik یازده رقمی با چک‌سام معتبر
    """
    clean_name = name.strip()
    clean_phone = phone.strip().replace(" ", "").replace("-", "") if phone else ""
    clean_nid = national_id.strip().replace(" ", "").replace("-", "") if national_id else None

    if len(clean_name) < 3:
        return (f"{party_type_label} adı en az 3 karakter olmalıdır.", clean_name, clean_phone, clean_nid)

    if not clean_phone:
        return (f"{party_type_label} için telefon numarası zorunludur.", clean_name, clean_phone, clean_nid)

    if not validate_turkish_phone(clean_phone):
        return ("Geçersiz telefon numarası. Telefon 05xx veya 02xx formatında 11 haneli olmalıdır (Örn: 05321234567).", clean_name, clean_phone, clean_nid)

    if clean_nid:
        if not clean_nid.isdigit():
            return ("Vergi Kimlik Numarası (VKN) veya T.C. Kimlik No sadece rakamlardan oluşmalıdır.", clean_name, clean_phone, clean_nid)
        
        if len(clean_nid) == 10:
            if not validate_vkn(clean_nid):
                return ("Girilen 10 haneli Vergi Kimlik Numarası (VKN) algoritma kontrolünden geçemedi (Geçersiz VKN).", clean_name, clean_phone, clean_nid)
        elif len(clean_nid) == 11:
            if not validate_tc_kimlik(clean_nid):
                return ("Girilen 11 haneli T.C. Kimlik Numarası algoritma kontrolünden geçemedi (Geçersiz TCKN).", clean_name, clean_phone, clean_nid)
        else:
            return ("Kurumsal firmalar için 10 haneli VKN, şahıslar için 11 haneli T.C. Kimlik Numarası girilmelidir.", clean_name, clean_phone, clean_nid)

    return (None, clean_name, clean_phone, clean_nid)


def validate_gtip(gtip: str) -> bool:
    """
    اعتبارسنجی کد تعرفه گمرکی ترکیه (GTİP - Gümrük Tarife İstatistik Pozisyonu)
    کد GTİP دقیقاً ۱۲ رقم عددی است (با یا بدون جداکننده نقطه).
    مثال: 7214.20.00.00.00 یا 721420000000
    """
    if not gtip:
        return False
    clean = str(gtip).strip().replace(".", "").replace(" ", "").replace("-", "")
    return len(clean) == 12 and clean.isdigit()


def format_gtip(gtip: str) -> str:
    """
    فرمت‌بندی استاندارد ۱۲ رقمی کد تعرفه گمرکی ترکیه به فرمت نقطه‌گذاری رسمی:
    XXXX.XX.XX.XX.XX
    """
    if not gtip:
        return ""
    clean = str(gtip).strip().replace(".", "").replace(" ", "").replace("-", "")
    if len(clean) == 12 and clean.isdigit():
        return f"{clean[0:4]}.{clean[4:6]}.{clean[6:8]}.{clean[8:10]}.{clean[10:12]}"
    return gtip


# ==============================================================================
# بخش ۵: پلاک انتظامی وسایل نقلیه سنگین ترکیه و استانداردهای راهداری (KGM)
# ==============================================================================

# ساختار رسمی پلاک ترکیه: ۲ رقم کد استان (۰۱ تا ۸۱) + ۱ تا ۳ حرف بدون حروف Q, W, X + ۲ تا ۴ رقم
# نمونه‌ها: 34 ABC 123, 06 TR 987, 35 A 4567, 41 K 892
TURKISH_PLATE_REGEX = re.compile(
    r"^(0[1-9]|[1-7][0-9]|8[01])\s*([A-PR-VYZ]{1,3})\s*(\d{2,4})$",
    re.IGNORECASE
)

def validate_turkish_plate(plate: str) -> bool:
    """
    اعتبارسنجی الگوریتم و ساختار پلاک خودروهای ترکیه مطابق استاندارد EGM و پلاک انتظامی
    - کد استان معتبر بین 01 تا 81
    - بخش حروفی بین 1 تا 3 حرف
    - بخش عددی بین 2 تا 4 رقم
    """
    if not plate:
        return False
    clean = str(plate).strip().upper()
    return bool(TURKISH_PLATE_REGEX.match(clean))


def format_turkish_plate(plate: str) -> str:
    """
    فرمت‌بندی خوانا و استاندارد پلاک ترکیه به صورت: [کد استان] [حروف] [اعداد]
    مثال: 34ABC123 -> 34 ABC 123
    """
    if not plate:
        return ""
    clean = str(plate).strip().upper()
    m = TURKISH_PLATE_REGEX.match(clean)
    if m:
        il_kodu, harfler, sayilar = m.groups()
        return f"{il_kodu} {harfler.upper()} {sayilar}"
    return clean


# استانداردهای مصوب سازمان راهداری و بزرگراه‌های ترکیه (Karayolları Genel Müdürlüğü - KGM)
# بر اساس ماده ۱۲۸ آیین‌نامه راهنمایی و رانندگی ترکیه
KGM_TRUCK_LIMITS = {
    # ۵ یا ۶ محور (تریلی کفی و ترانزیت استاندارد)
    "TIR_5AXIS": 40000.0,
    # حمل ترکیبی و کانتینری ۴۰ فوت ایزو (محدوده مجاز بنادر و راه‌آهن)
    "CONTAINER_40FT": 44000.0,
    # ۴ محور (کامیون‌های سنگین کمپرسی ۴ محور)
    "TRUCK_4AXIS": 32000.0,
    # ۳ محور (کامیون جفت ۱۰ چرخ)
    "TRUCK_3AXIS": 26000.0,
    # ۲ محور (کامیون تک ۶ چرخ)
    "TRUCK_2AXIS": 18000.0,
}

def check_kgm_weight_limit(gross_weight: float, truck_type: Optional[str] = None) -> Tuple[bool, float, str]:
    """
    کنترل تطابق وزن ناخالص با سقف قانونی راهداری ترکیه (KGM):
    خروجی: (آیا اضافه تناژ دارد؟, سقف مجاز قانونی, پیام هشدار رسمی)
    """
    default_limit = 40000.0  # ۴۰ تن برای تریلی‌های استاندارد فولادی و کفی
    if truck_type:
        t_lower = truck_type.lower()
        if "konteyner" in t_lower or "44" in t_lower:
            default_limit = 44000.0
        elif "4 dingil" in t_lower or "32" in t_lower:
            default_limit = 32000.0
        elif "3 dingil" in t_lower or "26" in t_lower or "جفت" in t_lower:
            default_limit = 26000.0
        elif "2 dingil" in t_lower or "18" in t_lower or "تک" in t_lower:
            default_limit = 18000.0

    is_overweight = gross_weight > default_limit
    if is_overweight:
        diff = gross_weight - default_limit
        msg = (
            f"KGM Azami Yüklü Ağırlık Sınırı Aşıldı! "
            f"Yasal Sınır: {default_limit:,.0f} kg | Tespit Edilen: {gross_weight:,.0f} kg | "
            f"Fazla Tonaj: +{diff:,.0f} kg"
        )
    else:
        msg = f"KGM Yasal Tartım Sınırları İçinde ({default_limit:,.0f} kg)"

    return (is_overweight, default_limit, msg)


