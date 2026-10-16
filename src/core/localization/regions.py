import os
import json
from datetime import datetime, date
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
from fastapi import Request
from jinja2 import pass_context

@dataclass
class RegionConfig:
    code: str                  # "IR" or "TR"
    name_fa: str              # "ایران" or "ترکیه"
    name_native: str          # "ایران" or "Türkiye"
    flag: str                 # "🇮🇷" or "🇹🇷"
    default_lang: str         # "fa" or "tr"
    dir: str                  # "rtl" or "ltr"
    currency_symbol: str      # "ریال" or "₺"
    currency_code: str        # "IRR" or "TRY"
    date_format: str          # "jalali" or "gregorian"
    tax_name: str             # "ارزش افزوده ۱۰٪" or "KDV (%20)"
    default_vat_rate: float   # 0.10 or 0.20
    identity_label: str       # "شناسه ملی / کد اقتصادی" or "VKN / T.C. Kimlik No"
    plate_format: str         # "iran_smart" or "turkey_standard"
    compliance_name: str      # "سامانه جامع تجارت" or "e-İrsaliye & GİB / U-ETDS"
    tagline: str              # شرح کوتاه سازمانی


class Region:
    IR = "IR"
    TR = "TR"


REGIONS: Dict[str, RegionConfig] = {
    Region.IR: RegionConfig(
        code="IR",
        name_fa="ایران",
        name_native="ایران",
        flag="🇮🇷",
        default_lang="fa",
        dir="rtl",
        currency_symbol="ریال",
        currency_code="IRR",
        date_format="jalali",
        tax_name="مالیات بر ارزش افزوده (۱۰٪)",
        default_vat_rate=0.10,
        identity_label="شناسه ملی / کد اقتصادی",
        plate_format="iran_smart",
        compliance_name="سامانه جامع تجارت و انبارها",
        tagline="سامانه جامع انبارداری و زنجیره تأمین صنایع سنگین"
    ),
    Region.TR: RegionConfig(
        code="TR",
        name_fa="ترکیه",
        name_native="Türkiye",
        flag="🇹🇷",
        default_lang="tr",
        dir="ltr",
        currency_symbol="₺",
        currency_code="TRY",
        date_format="gregorian",
        tax_name="Katma Değer Vergisi (%20 KDV)",
        default_vat_rate=0.20,
        identity_label="VKN / T.C. Kimlik No",
        plate_format="turkey_standard",
        compliance_name="e-İrsaliye, GİB & U-ETDS",
        tagline="Ağır Sanayi ve Çelik Depo Yönetim Sistemi"
    )
}

# کش فایل‌های ترجمه در حافظه
_TRANSLATION_CACHE: Dict[str, Dict[str, Any]] = {}

def get_locale_dict(lang: str = "fa") -> Dict[str, Any]:
    """خواندن و کش کردن فایل ترجمه json متناسب با زبان"""
    lang = lang.lower()
    if lang not in ("fa", "tr"):
        lang = "fa"

    if lang in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[lang]

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    locale_path = os.path.join(base_dir, "locales", f"{lang}.json")

    if not os.path.exists(locale_path):
        # fallback to fa
        locale_path = os.path.join(base_dir, "locales", "fa.json")

    try:
        with open(locale_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _TRANSLATION_CACHE[lang] = data
            return data
    except Exception:
        return {}


def get_translation(key_path: str, lang: str = "fa") -> str:
    """دریافت ترجمه یک کلید با ساختار نقطه‌ای مانند system.brand_title"""
    data = get_locale_dict(lang)
    parts = key_path.split(".")
    val = data
    for p in parts:
        if isinstance(val, dict) and p in val:
            val = val[p]
        else:
            # Fallback to Persian if not in current lang
            if lang != "fa":
                fa_data = get_locale_dict("fa")
                fa_val = fa_data
                for fp in parts:
                    if isinstance(fa_val, dict) and fp in fa_val:
                        fa_val = fa_val[fp]
                    else:
                        return key_path
                return str(fa_val)
            return key_path
    return str(val)


def get_active_region(request: Request) -> RegionConfig:
    """
    تشخیص منطقه فعال سامانه با اولویت حالت ارزی ماژولار:
    اگر حالت ارزی فقط ترکیه (TR_ONLY) باشد -> ترکیه تثبیت می‌شود.
    اگر حالت ارزی فقط ایران (IR_ONLY) باشد -> ایران تثبیت می‌شود.
    در حالت ALL (دو ارزی) -> کوکی nexus_region اولویت دارد.
    """
    from src.core.modules import get_currency_mode
    mode = get_currency_mode()
    if mode == "TR_ONLY":
        return REGIONS[Region.TR]
    elif mode == "IR_ONLY":
        return REGIONS[Region.IR]

    code = request.cookies.get("nexus_region")
    if not code:
        code = os.getenv("DEFAULT_REGION", Region.IR)

    code = code.upper().strip()
    return REGIONS.get(code, REGIONS[Region.IR])



def format_currency(amount: float, region_code: str = "IR") -> str:
    """فرمت‌بندی مبلغ متناسب با واحد پولی کشور"""
    try:
        formatted_num = f"{amount:,.0f}"
    except (ValueError, TypeError):
        formatted_num = "0"

    cfg = REGIONS.get(region_code, REGIONS[Region.IR])
    if cfg.code == Region.TR:
        return f"{formatted_num} {cfg.currency_symbol}"
    return f"{formatted_num} {cfg.currency_symbol}"


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> Tuple[int, int, int]:
    """
    الگوریتم دقیق و خالص ریاضی بدون وابستگی خارجی جهت تبدیل تقویم میلادی به خورشیدی (شمسی)
    """
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy if gm > 2 else gy - 1
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return (jy, jm, jd)


def format_date_localized(dt_val: Any, region_code: str = "IR", include_time: bool = False) -> str:
    """
    فرمت‌بندی تاریخ بر اساس استاندارد کشور مقصد:
    - در ایران (IR): تاریخ شمسی رسمی (مثلاً 1405/07/23)
    - در ترکیه (TR): فرمت تقویمی رسمی ترکیه (DD.MM.YYYY مثلاً 15.10.2026)
    """
    if not dt_val:
        return "-"

    dt = dt_val
    if isinstance(dt_val, str):
        s = dt_val.strip()
        if not s or s == "-":
            return "-"
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            try:
                dt = datetime.strptime(s[:10], "%Y-%m-%d")
            except Exception:
                return s

    if hasattr(dt, "year") and hasattr(dt, "month") and hasattr(dt, "day"):
        y, m, d = dt.year, dt.month, dt.day
        hour = getattr(dt, "hour", 0)
        minute = getattr(dt, "minute", 0)

        reg = (region_code or "IR").upper()
        if reg == "TR":
            date_str = f"{d:02d}.{m:02d}.{y:04d}"
        else:
            jy, jm, jd = gregorian_to_jalali(y, m, d)
            date_str = f"{jy:04d}/{jm:02d}/{jd:02d}"

        if include_time and hasattr(dt, "hour"):
            return f"{date_str} {hour:02d}:{minute:02d}"
        return date_str

    return str(dt_val)


@pass_context
def format_date_filter(context, value, region: Any = None, include_time: bool = False) -> str:
    """فیلتر Jinja2 برای نمایش هوشمند تاریخ در قالب‌ها با پشتیبانی از شمسی (ایران) و رسمی ترکیه"""
    if not value:
        return "-"
    reg = "IR"
    if isinstance(region, bool):
        reg = "TR" if region else "IR"
    elif isinstance(region, str):
        reg = region.upper()
    else:
        if context.get("is_tr") is True:
            reg = "TR"
        else:
            active_reg = context.get("active_region")
            if hasattr(active_reg, "code"):
                reg = active_reg.code
            elif isinstance(active_reg, dict) and "code" in active_reg:
                reg = active_reg.get("code", "IR")
            else:
                req = context.get("request")
                if req and hasattr(req, "cookies"):
                    reg = req.cookies.get("nexus_region", "IR")

    return format_date_localized(value, region_code=reg or "IR", include_time=include_time)


def register_jinja_filters(jinja_templates: Any):
    """ثبت فیلترهای بومی‌سازی دو زبانه و متغیرهای جهانی ماژولار در نمونه Jinja2Templates"""
    from src.core.modules import load_modules_config, is_module_enabled, get_currency_mode
    jinja_templates.env.filters["tr_loc"] = localize_display_name
    jinja_templates.env.filters["format_date"] = format_date_filter
    jinja_templates.env.filters["format_currency"] = format_currency
    jinja_templates.env.globals["get_system_modules"] = load_modules_config
    jinja_templates.env.globals["is_module_enabled"] = is_module_enabled
    jinja_templates.env.globals["get_currency_mode"] = get_currency_mode



# دیکشنری جامع ترجمه و بومی‌سازی داده‌های پایه (کالاها، دسته‌بندی‌ها، انبارها، واحدها و برندها)
TR_MASTER_DATA_MAP: Dict[str, str] = {
    # اقلام و محصولات فولادی و شیمیایی
    # ۱. شمش فولادی و آهن
    "شمش فولادی ۱۵۰×۱۵۰": "Sürekli Döküm Çelik Kütük 150×150mm",
    "شمش فولادی 150*150": "Sürekli Döküm Çelik Kütük 150×150mm",
    "شمش فولادی 150×150": "Sürekli Döküm Çelik Kütük 150×150mm",
    "شمش فولادی ۱۳۰×۱۳۰": "Sürekli Döküm Çelik Kütük 130×130mm",
    "شمش فولادی 130*130": "Sürekli Döküm Çelik Kütük 130×130mm",
    "شمش فولادی 130×130": "Sürekli Döküm Çelik Kütük 130×130mm",
    "شمش فولادی": "Sürekli Döküm Çelik Kütük",
    "شمش آهن": "Çelik Kütük (Demir Kütük)",
    "شمش بیلت فولادی ۱۵۰×۱۵۰ S235JR": "Sürekli Döküm Çelik Kütük 150×150mm S235JR",
    "شمش بیلت فولادی 150×150 S235JR": "Sürekli Döküm Çelik Kütük 150×150mm S235JR",
    "شمش بیلت فولادی ۱۳۰×۱۳۰ 3SP": "Sürekli Döküm Çelik Kütük 130×130mm 3SP",
    "شمش بیلت فولادی 130×130 3SP": "Sürekli Döküm Çelik Kütük 130×130mm 3SP",
    "آهن": "Demir ve Çelik",
    "آهن‌آلات": "Demir ve Çelik Ürünleri",

    # ۲. میلگرد در ابعاد و سایزهای مختلف
    "میلگرد آجدار سایز ۱۴ (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø14mm B420B (12m)",
    "میلگرد آجدار سایز 14 (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø14mm B420B (12m)",
    "میلگرد آجدار ۱۴ میلی‌متر B420B (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø14mm B420B (12m)",
    "میلگرد آجدار 14 میلی‌متر B420B (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø14mm B420B (12m)",
    "میلگرد آجدار ۱۴": "Nervürlü İnşaat Demiri Ø14mm",
    "میلگرد آجدار 14": "Nervürlü İnşaat Demiri Ø14mm",
    "میلگرد ۱۴": "Nervürlü İnşaat Demiri Ø14mm",
    "میلگرد 14": "Nervürlü İnşaat Demiri Ø14mm",

    "میلگرد آجدار سایز ۱۶ (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار سایز 16 (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار ۱۶ میلی‌متر B420B (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار 16 میلی‌متر B420B (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار ۱۶": "Nervürlü İnşaat Demiri Ø16mm",
    "میلگرد آجدار 16": "Nervürlü İnşaat Demiri Ø16mm",
    "میلگرد ۱۶": "Nervürlü İnşaat Demiri Ø16mm",
    "میلگرد 16": "Nervürlü İnşaat Demiri Ø16mm",

    "میلگرد آجدار سایز ۱۸ (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø18mm B420B (12m)",
    "میلگرد آجدار سایز 18 (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø18mm B420B (12m)",
    "میلگرد آجدار ۱۸ میلی‌متر B420B (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø18mm B420B (12m)",
    "میلگرد آجدار 18 میلی‌متر B420B (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø18mm B420B (12m)",
    "میلگرد آجدار ۱۸": "Nervürlü İnşaat Demiri Ø18mm",
    "میلگرد آجدار 18": "Nervürlü İnşaat Demiri Ø18mm",
    "میلگرد ۱۸": "Nervürlü İnşaat Demiri Ø18mm",
    "میلگرد 18": "Nervürlü İnşaat Demiri Ø18mm",

    "میلگرد آجدار سایز ۲۰ (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø20mm B420B (12m)",
    "میلگرد آجدار سایز 20 (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø20mm B420B (12m)",
    "میلگرد آجدار ۲۰ میلی‌متر B420B (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø20mm B420B (12m)",
    "میلگرد آجدار 20 میلی‌متر B420B (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø20mm B420B (12m)",
    "میلگرد آجدار ۲۰": "Nervürlü İnşaat Demiri Ø20mm",
    "میلگرد آجدار 20": "Nervürlü İnşaat Demiri Ø20mm",
    "میلگرد ۲۰": "Nervürlü İnşaat Demiri Ø20mm",
    "میلگرد 20": "Nervürlü İnşaat Demiri Ø20mm",

    "میلگرد آجدار سایز ۲۲ (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø22mm B420B (12m)",
    "میلگرد آجدار سایز 22 (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø22mm B420B (12m)",
    "میلگرد آجدار ۲۲": "Nervürlü İnşaat Demiri Ø22mm",
    "میلگرد آجدار 22": "Nervürlü İnşaat Demiri Ø22mm",
    "میلگرد ۲۲": "Nervürlü İnşaat Demiri Ø22mm",
    "میلگرد 22": "Nervürlü İnşaat Demiri Ø22mm",
    "میلگرد": "Nervürlü İnşaat Demiri",

    # ۳. تیرآهن و پروفیل‌های ساختمانی
    "تیرآهن IPE 14": "IPE 140 Yapısal Çelik Profil",
    "تیرآهن IPE 14 (شاخه ۱۲ متری)": "IPE 140 Yapısal Çelik Profil (12m)",
    "تیرآهن IPE 14 (شاخه 12 متری)": "IPE 140 Yapısal Çelik Profil (12m)",
    "تیرآهن ۱۴": "IPE 140 Yapısal Çelik Profil",
    "تیرآهن 14": "IPE 140 Yapısal Çelik Profil",

    "تیرآهن IPE 16": "IPE 160 Yapısal Çelik Profil",
    "تیرآهن IPE 16 (شاخه ۱۲ متری)": "IPE 160 Yapısal Çelik Profil (12m)",
    "تیرآهن IPE 16 (شاخه 12 متری)": "IPE 160 Yapısal Çelik Profil (12m)",
    "تیرآهن ۱۶": "IPE 160 Yapısal Çelik Profil",
    "تیرآهن 16": "IPE 160 Yapısal Çelik Profil",

    "تیرآهن IPE 18": "IPE 180 Yapısal Çelik Profil",
    "تیرآهن IPE 18 (شاخه ۱۲ متری)": "IPE 180 Yapısal Çelik Profil (12m)",
    "تیرآهن IPE 18 (شاخه 12 متری)": "IPE 180 Yapısal Çelik Profil (12m)",
    "تیرآهن ۱۸": "IPE 180 Yapısal Çelik Profil",
    "تیرآهن 18": "IPE 180 Yapısal Çelik Profil",

    "تیرآهن IPE 20": "IPE 200 Yapısal Çelik Profil",
    "تیرآهن IPE 20 (شاخه ۱۲ متری)": "IPE 200 Yapısal Çelik Profil (12m)",
    "تیرآهن IPE 20 (شاخه 12 متری)": "IPE 200 Yapısal Çelik Profil (12m)",
    "تیرآهن ۲۰": "IPE 200 Yapısal Çelik Profil",
    "تیرآهن 20": "IPE 200 Yapısal Çelik Profil",
    "تیرآهن": "Yapısal Çelik Profil",

    # ۴. اوره و کودهای شیمیایی
    "اوره گرانول صادراتی (فله)": "Granül Üre Gübresi %46 Azot (Dökme)",
    "اوره گرانول": "Granül Üre Gübresi %46",
    "کود اوره گرانول ۴۶ درصد ازت (فله)": "Granül Üre Gübresi %46 Azot (Dökme)",
    "کود اوره گرانول 46 درصد ازت (فله)": "Granül Üre Gübresi %46 Azot (Dökme)",
    "کود اوره گرانول ۴۶ درصد ازت (فله و جامبوبگ)": "Granül Üre Gübresi %46 Azot (Dökme & Big Bag)",
    "کود اوره گرانول 46 درصد ازت (فله و جامبوبگ)": "Granül Üre Gübresi %46 Azot (Dökme & Big Bag)",
    "کود اوره گرانول ۴۶ درصد ازت (جامبوبگ ۱ تنی)": "Granül Üre Gübresi %46 Azot (1 Tonluk Big-Bag)",
    "کود اوره گرانول 46 درصد ازت (جامبوبگ 1 تنی)": "Granül Üre Gübresi %46 Azot (1 Tonluk Big-Bag)",
    "کود اوره ۵۰ کیلویی لمینت": "50 kg Torbalı Granül Üre Gübresi",
    "کود اوره 50 کیلویی لمینت": "50 kg Torbalı Granül Üre Gübresi",
    "کود اوره گرانول": "Granül Üre Gübresi",
    "کود اوره": "Üre Gübresi",
    "اوره": "Üre",

    # ۵. ورق و کلاف فولادی
    "کلاف گرم فولادی (ورق سیاه رول HRC)": "Sıcak Haddelenmiş Rulo Sac (HRC)",
    "کلاف گرم فولادی": "Sıcak Haddelenmiş Rulo Sac (HRC)",
    "ورق سیاه برشی فولادی (شیت ۱۰ میل)": "Sıcak Haddelenmiş Plaka Sac (10mm)",
    "ورق سیاه برشی فولادی (شیت 10 میل)": "Sıcak Haddelenmiş Plaka Sac (10mm)",
    "ورق سیاه فولادی": "Sıcak Haddelenmiş Siyah Sac",
    "ورق سیاه": "Siyah Sac",
    "ورق گالوانیزه": "Galvanizli Sac",
    "نبشی": "Köşebent Profil",
    "ناودانی": "U Profil",
    "پروفیل قوطی": "Kutu Profil",
    "لوله مانیسمان": "Dikişsiz Çelik Boru (Mannesmann)",
    "قراضه سنگین ذوبی (ویژه)": "Ağır Ergitme Çelik Hurdası (HMS 1)",
    "قراضه آهن": "Demir Çelik Hurdası",
    "ضایعات آهن": "Hurda Demir",
    "کیسه جامبوبگ ۱ تنی": "1 Tonluk Big-Bag Torba",
    "کیسه جامبوبگ 1 تنی": "1 Tonluk Big-Bag Torba",
    "کیسه ۵۰ کیلویی لمینت": "50 kg Lamineli Torba",
    "کیسه 50 کیلویی لمینت": "50 kg Lamineli Torba",

    # دسته‌بندی‌های کالا
    "مقاطع و شمش فولادی": "Çelik Kütük ve Profil Ürünleri",
    "مواد شیمیایی و پتروشیمی": "Kimyasal ve Petrokimya Ürünleri",
    "لوله و پروفیل صنعتی": "Sanayi Boru ve Profil",
    "ملزومات بسته‌بندی و پالت": "Paketleme ve Palet Malzemeleri",
    "فلزات و آهن‌آلات": "Demir ve Çelik Ürünleri",
    "مواد اولیه": "Hammadde",
    "کالای نهایی": "Bitmiş Ürünler",
    "قطعات یدکی": "Yedek Parça",
    "ضایعات و بازیافت": "Hurda ve Geri Kazanım",

    # انبارها
    "انبار شماره یک (محوطه سنگین و شمش)": "1 Nolu Açık Saha Deposu (Kütük ve Ağır Çelik)",
    "انبار شماره دو (سوله مسقف و شیمیایی)": "2 Nolu Kapalı Depo (Kimyasal ve Gübre)",
    "انبار شماره یک": "1 Nolu Açık Saha Deposu",
    "انبار شماره دو": "2 Nolu Kapalı Depo",
    "انبار شماره ۱": "1 Nolu Depo",
    "انبار شماره ۲": "2 Nolu Depo",
    "انبار مرکزی": "Merkez Depo",
    "انبار مرکزی تهران": "İstanbul / Tahran Merkez Deposu",
    "انبار روباز تیرآهن و میلگرد": "Açık Profil ve İnşaat Demiri Deposu",
    "انبار قطعات": "Yedek Parça Deposu",
    "انبار مواد اولیه": "Hammadde Deposu",
    "انبار محصول نهایی": "Mamul Deposu",
    "انبار ضایعات و قراضه": "Hurda ve İkincil Ürün Deposu",
    "انبار ضایعات": "Hurda Deposu",
    "انبار قراضه": "Hurda Deposu",
    "انبار برش": "Kesim Sahası Deposu",
    "انبار ته‌شاخه‌ها": "Kalan Parça ve Kesim Deposu",

    # واحدهای سنجش (UOM)
    "کیلوگرم": "kg",
    "تن": "ton",
    "شاخه": "çubuk",
    "بندیل": "bağ",
    "قالب": "blok",
    "کوتوک": "kütük",
    "جامبوبگ": "big-bag",
    "کیسه": "torba",
    "متر": "m",
    "عدد": "adet",
    "بسته": "paket",
    "رول": "rulo",
    "ورق": "levha",
    "دستگاه": "cihaz",

    # کارخانجات و برندهای مادر
    "فولاد خوزستان": "KSC Steel",
    "پتروشیمی پردیس": "Pardis Petrokimya",
    "فولاد نیشابور": "Neyshabur Steel",
    "ذوب‌آهن اصفهان": "İsfahan Çelik (ESCO)",
    "فولاد مبارکه": "Mobarakeh Çelik",

    # تأمین‌کنندگان (Suppliers)
    "مجتمع فولاد مبارکه اصفهان": "Mobarakeh Çelik Sanayi A.Ş.",
    "تأمین‌کننده فرضی ۱ (مجتمع فولاد مبارکه اصفهان)": "Mobarakeh Çelik Sanayi A.Ş.",
    "شرکت سهامی ذوب‌آهن اصفهان": "İsfahan Demir Çelik Fabrikaları (ESCO)",
    "تأمین‌کننده فرضی ۲ (شرکت سهامی ذوب‌آهن اصفهان)": "İsfahan Demir Çelik Fabrikaları (ESCO)",
    "شرکت پتروشیمی پردیس عسلویه": "Pardis Petrokimya Kompleksi (Assaluyeh)",
    "تأمین‌کننده فرضی ۳ (شرکت پتروشیمی پردیس عسلویه)": "Pardis Petrokimya Kompleksi (Assaluyeh)",
    "شرکت فولاد خوزستان": "Khouzestan Çelik Sanayi (KSC)",
    "مجتمع فولاد خراسان (نیشابور)": "Khorasan (Neyshabur) Çelik Kompleksi",
    "Ereğli Demir ve Çelik Fabrikaları T.A.Ş. (Erdemir)": "Ereğli Demir ve Çelik Fabrikaları T.A.Ş. (Erdemir)",
    "İskenderun Demir ve Çelik A.Ş. (İsdemir)": "İskenderun Demir ve Çelik A.Ş. (İsdemir)",
    "Karabük Demir Çelik Sanayi ve Ticaret A.Ş. (Kardemir)": "Karabük Demir Çelik Sanayi ve Ticaret A.Ş. (Kardemir)",
    "Toros Tarım ve Gübre Sanayi A.Ş. (Toros Gübre)": "Toros Tarım ve Gübre Sanayi A.Ş. (Toros Gübre)",
    "Tosyalı Demir Çelik Sanayi A.Ş.": "Tosyalı Demir Çelik Sanayi A.Ş.",

    # مشتریان و خریداران (Customers)
    "پروژه ساختمانی برج آرمان امید": "Arman Kule İnşaat Projesi",
    "مشتری فرضی ۱ (پروژه ساختمانی برج آرمان امید)": "Arman Kule İnşaat Projesi",
    "شرکت مهندسی و توسعه خطوط لوله پارس": "Pars Boru Hatları Mühendislik ve Geliştirme A.Ş.",
    "مشتری فرضی ۲ (شرکت مهندسی و توسعه خطوط لوله پارس)": "Pars Boru Hatları Mühendislik ve Geliştirme A.Ş.",
    "بازرگانی صنایع فلزی کاوه": "Kaveh Metal Sanayi ve Ticaret",
    "مشتری فرضی ۳ (بازرگانی صنایع فلزی کاوه)": "Kaveh Metal Sanayi ve Ticaret",
    "شرکت سازه‌های فولادی البرز": "Alborz Çelik Yapı Sanayi A.Ş.",
    "مجتمع کشت و صنعت مغان": "Mogan Tarım ve Hayvancılık Kompleksi",
    "Rönesans Holding / İnşaat Sanayi ve Ticaret A.Ş.": "Rönesans Holding / İnşaat Sanayi ve Ticaret A.Ş.",
    "ENKA İnşaat ve Sanayi A.Ş.": "ENKA İnşaat ve Sanayi A.Ş.",
    "Marmara Çelik Profil ve Dış Ticaret Ltd. Şti.": "Marmara Çelik Profil ve Dış Ticaret Ltd. Şti.",

    # انواع خودرو و ناوگان حمل و نقل
    "تریلی کفی ۱۸ چرخ (بندیل و میلگرد)": "Standart 5 Dingilli Açık Kasa Treyler (Tır)",
    "تریلی کفی ۱۸ چرخ": "Standart 5 Dingilli Açık Kasa Treyler (Tır)",
    "تریلی لبه‌دار / ترانزیت": "Tenteli / Kapalı Kasa Tır",
    "کمپرسی سنگین (فله و شمش)": "Ağır Tonajlı Damperli Kamyon",
    "کمپرسی سنگین": "Ağır Tonajlı Damperli Kamyon",
    "کامیون جفت (۱۰ چرخ)": "3 Dingilli Kamyon (26 Ton)",
    "کامیون تک (۶ چرخ)": "2 Dingilli Kamyon (18 Ton)",
}

# دیکشنری نگاشت معکوس (ترکی به فارسی)
IR_MASTER_DATA_MAP: Dict[str, str] = {
    "Nervürlü İnşaat Demiri Ø16mm B420B (12m)": "میلگرد آجدار ۱۶ میلی‌متر B420B (شاخه ۱۲ متری)",
    "Nervürlü İnşaat Demiri Ø14mm B420B (12m)": "میلگرد آجدار سایز ۱۴ (شاخه ۱۲ متری)",
    "Nervürlü İnşaat Demiri Ø18mm B420B (12m)": "میلگرد آجدار سایز ۱۸ (شاخه ۱۲ متری)",
    "Nervürlü İnşaat Demiri Ø20mm B420B (12m)": "میلگرد آجدار سایز ۲۰ (شاخه ۱۲ متری)",
    "Nervürlü İnşaat Demiri Ø22mm B420B (12m)": "میلگرد آجدار سایز ۲۲ (شاخه ۱۲ متری)",
    "IPE 140 Yapısal Çelik Profil": "تیرآهن IPE 14",
    "IPE 160 Yapısal Çelik Profil": "تیرآهن IPE 16",
    "IPE 180 Yapısal Çelik Profil": "تیرآهن IPE 18",
    "IPE 200 Yapısal Çelik Profil": "تیرآهن IPE 20",
    "Sürekli Döküm Çelik Kütük 150×150mm S235JR": "شمش بیلت فولادی ۱۵۰×۱۵۰ S235JR",
    "Sürekli Döküm Çelik Kütük 150×150mm": "شمش فولادی ۱۵۰×۱۵۰",
    "Sürekli Döküm Çelik Kütük 130×130mm": "شمش فولادی ۱۳۰×۱۳۰",
    "Sürekli Döküm Çelik Kütük": "شمش فولادی",
    "Granül Üre Gübresi %46 Azot (Dökme & Big Bag)": "کود اوره گرانول ۴۶ درصد ازت (فله و جامبوبگ)",
    "Granül Üre Gübresi %46 Azot (Dökme)": "اوره گرانول صادراتی (فله)",
    "Granül Üre Gübresi %46 Azot (1 Tonluk Big-Bag)": "کود اوره گرانول ۴۶ درصد ازت (جامبوبگ ۱ تنی)",
    "50 kg Torbalı Granül Üre Gübresi": "کود اوره ۵۰ کیلویی لمینت",
    "Sıcak Haddelenmiş Rulo Sac (HRC)": "کلاف گرم فولادی (ورق سیاه رول HRC)",
    "Sıcak Haddelenmiş Plaka Sac (10mm)": "ورق سیاه برشی فولادی (شیت ۱۰ میل)",
    "1 Nolu Açık Saha Deposu (Kütük ve Ağır Çelik)": "انبار شماره یک (محوطه سنگین و شمش)",
    "2 Nolu Kapalı Depo (Kimyasal ve Gübre)": "انبار شماره دو (سوله مسقف و شیمیایی)",
    "Açık Profil ve İnşaat Demiri Deposu": "انبار روباز تیرآهن و میلگرد",
    "İstanbul / Tahran Merkez Deposu": "انبار مرکزی تهران",
    "Kalan Parça ve Kesim Deposu": "انبار ته‌شاخه‌ها",
    "Standart 5 Dingilli Açık Kasa Treyler (Tır)": "تریلی کفی ۱۸ چرخ (بندیل و میلگرد)",
    "Tenteli / Kapalı Kasa Tır": "تریلی لبه‌دار / ترانزیت",
    "Ağır Tonajlı Damperli Kamyon": "کمپرسی سنگین (فله و شمش)",
    "3 Dingilli Kamyon (26 Ton)": "کامیون جفت (۱۰ چرخ)",
    "2 Dingilli Kamyon (18 Ton)": "کامیون تک (۶ چرخ)",
    "Arman Kule İnşaat Projesi": "پروژه ساختمانی برج آرمان امید",
    "Pars Boru Hatları Mühendislik ve Geliştirme A.Ş.": "شرکت مهندسی و توسعه خطوط لوله پارس",
    "Kaveh Metal Sanayi ve Ticaret": "بازرگانی صنایع فلزی کاوه",
    "Ereğli Demir ve Çelik Fabrikaları T.A.Ş. (Erdemir)": "فولاد اردمیر ترکیه (Erdemir)",
    "İskenderun Demir ve Çelik A.Ş. (İsdemir)": "فولاد ایسدمیر ترکیه (İsdemir)",
    "Karabük Demir Çelik Sanayi ve Ticaret A.Ş. (Kardemir)": "فولاد کاردمیر ترکیه (Kardemir)",
    "Toros Tarım ve Gübre Sanayi A.Ş. (Toros Gübre)": "صنایع کود و شیمیایی توروس ترکیه",
    "Rönesans Holding / İnşaat Sanayi ve Ticaret A.Ş.": "هلدینگ ساختمانی رونسانس ترکیه",
    "ENKA İnşaat ve Sanayi A.Ş.": "شرکت ساختمانی انکا ترکیه",
    "Marmara Çelik Profil ve Dış Ticaret Ltd. Şti.": "شرکت پروفیل مرمره ترکیه",
}

# خودکارسازی نگاشت معکوس برای کلیه موارد تعریف شده در دیکشنری
for _fa, _tr in TR_MASTER_DATA_MAP.items():
    if _tr not in IR_MASTER_DATA_MAP:
        IR_MASTER_DATA_MAP[_tr] = _fa


def localize_display_name(name: Optional[str], is_tr: bool = False) -> str:
    """
    ترجمه هوشمند و بدون بازگشت نام کالاها، دسته‌بندی‌ها، انبارها، طرف‌های حساب و واحدها متناسب با منطقه فعال
    """
    if not name:
        return ""
    trimmed = str(name).strip()
    if is_tr:
        return TR_MASTER_DATA_MAP.get(trimmed, trimmed)
    return IR_MASTER_DATA_MAP.get(trimmed, trimmed)


