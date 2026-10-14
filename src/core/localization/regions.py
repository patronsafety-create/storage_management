import os
import json
from dataclasses import dataclass
from typing import Dict, Any, Optional
from fastapi import Request

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
    تشخیص منطقه فعال سامانه:
    اولویت ۱: کوکی nexus_region
    اولویت ۲: متغیر محیطی DEFAULT_REGION
    پیش‌فرض ایمن: IR (ایران)
    """
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


# دیکشنری جامع ترجمه و بومی‌سازی داده‌های پایه (کالاها، دسته‌بندی‌ها، انبارها، واحدها و برندها)
TR_MASTER_DATA_MAP: Dict[str, str] = {
    # اقلام و محصولات فولادی و شیمیایی
    "شمش فولادی ۱۵۰×۱۵۰": "Sürekli Döküm Çelik Kütük 150×150mm",
    "شمش فولادی 150*150": "Sürekli Döküm Çelik Kütük 150×150mm",
    "شمش فولادی 150×150": "Sürekli Döküm Çelik Kütük 150×150mm",
    "شمش فولادی": "Sürekli Döküm Çelik Kütük",
    "شمش بیلت فولادی ۱۵۰×۱۵۰ S235JR": "Sürekli Döküm Çelik Kütük 150×150mm S235JR",
    "شمش بیلت فولادی 150×150 S235JR": "Sürekli Döküm Çelik Kütük 150×150mm S235JR",
    "میلگرد آجدار سایز ۱۶ (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار سایز 16 (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار ۱۶ میلی‌متر B420B (شاخه ۱۲ متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار 16 میلی‌متر B420B (شاخه 12 متری)": "Nervürlü İnşaat Demiri Ø16mm B420B (12m)",
    "میلگرد آجدار ۱۶": "Nervürlü İnşaat Demiri Ø16mm",
    "میلگرد آجدار 16": "Nervürlü İnşaat Demiri Ø16mm",
    "میلگرد آجدار": "Nervürlü İnşaat Demiri",
    "اوره گرانول صادراتی (فله)": "Granül Üre Gübresi %46 Azot (Dökme)",
    "اوره گرانول": "Granül Üre Gübresi %46",
    "کود اوره گرانول ۴۶ درصد ازت (فله و جامبوبگ)": "Granül Üre Gübresi %46 Azot (Dökme & Big Bag)",
    "کود اوره گرانول 46 درصد ازت (فله و جامبوبگ)": "Granül Üre Gübresi %46 Azot (Dökme & Big Bag)",
    "کود اوره گرانول": "Granül Üre Gübresi",
    "کود اوره": "Üre Gübresi",
    "کلاف گرم فولادی": "Sıcak Haddelenmiş Rulo Sac (HRC)",
    "تیرآهن IPE 20": "IPE 200 Yapısal Çelik Profil",
    "تیرآهن IPE 18": "IPE 180 Yapısal Çelik Profil",
    "تیرآهن IPE 16": "IPE 160 Yapısal Çelik Profil",
    "تیرآهن": "Yapısal Çelik Profil",
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
    "انبار قطعات": "Yedek Parça Deposu",
    "انبار مواد اولیه": "Hammadde Deposu",
    "انبار محصول نهایی": "Mamul Deposu",
    "انبار ضایعات و قراضه": "Hurda ve İkincil Ürün Deposu",
    "انبار ضایعات": "Hurda Deposu",
    "انبار قراضه": "Hurda Deposu",
    "انبار برش": "Kesim Sahası Deposu",

    # واحدهای سنجش (UOM)
    "کیلوگرم": "kg",
    "تن": "ton",
    "شاخه": "çubuk",
    "بندیل": "bağ",
    "قالب": "blok",
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

    # انواع خودرو و ناوگان حمل و نقل
    "تریلی کفی ۱۸ چرخ (بندیل و میلگرد)": "Standart 5 Dingilli Açık Kasa Treyler (Tır)",
    "تریلی لبه‌دار / ترانزیت": "Tenteli / Kapalı Kasa Tır",
    "کمپرسی سنگین (فله و شمش)": "Ağır Tonajlı Damperli Kamyon",
    "کامیون جفت (۱۰ چرخ)": "3 Dingilli Kamyon (26 Ton)",
    "کامیون تک (۶ چرخ)": "2 Dingilli Kamyon (18 Ton)",
}

IR_MASTER_DATA_MAP: Dict[str, str] = {
    "Nervürlü İnşaat Demiri Ø16mm B420B (12m)": "میلگرد آجدار ۱۶ میلی‌متر B420B (شاخه ۱۲ متری)",
    "Sürekli Döküm Çelik Kütük 150×150mm S235JR": "شمش بیلت فولادی ۱۵۰×۱۵۰ S235JR",
    "Granül Üre Gübresi %46 Azot (Dökme & Big Bag)": "کود اوره گرانول ۴۶ درصد ازت (فله و جامبوبگ)",
}

def localize_display_name(name: Optional[str], is_tr: bool = False) -> str:
    """
    ترجمه هوشمند و بدون بازگشت نام کالاها، دسته‌بندی‌ها، انبارها و واحدها متناسب با منطقه فعال
    """
    if not name:
        return ""
    trimmed = str(name).strip()
    if is_tr:
        return TR_MASTER_DATA_MAP.get(trimmed, trimmed)
    return IR_MASTER_DATA_MAP.get(trimmed, trimmed)

