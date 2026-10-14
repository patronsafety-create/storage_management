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
