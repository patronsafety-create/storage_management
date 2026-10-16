"""
ماژول مرکزی نسخه‌بندی و ثبت تاریخچه تغییرات و انتشارات (Semantic Versioning & Enterprise Changelog)
طراحی و مهندسی: امید پورمحمود (Omid Pourmahmoud)
سامانه: NexusPour Enterprise ERP
"""
import os
import json
from datetime import datetime
from typing import List, Dict, Any

CURRENT_VERSION = "3.2.2"
CHANGELOG_FILE = "storage_changelog.json"

DEFAULT_RELEASE_HISTORY: List[Dict[str, Any]] = [
    {
        "version": "3.2.2",
        "date": "۱۴۰۵/۰۷/۲۵ - 2026-10-16",
        "title": "ارتقاء پیشخوان اجرایی مدیریت: رفع باگ‌های بصری، نرمال‌سازی تناژ و کنترل‌های تعاملی پیشرفته",
        "badge": "Current Enterprise",
        "badge_color": "success",
        "categories": {
            "🚀 Architecture & Features": [
                "نرمال‌سازی کامل واحدهای سنجش: تبدیل خودکار کیلوگرم به تن قبل از تجمیع شاخص‌های وزنی کل انبار و بارهای در راه خرید.",
                "فیلتر و پاکسازی انبارهای تستی بی‌استفاده صفرموجودی از لیست ظرفیت و شاخص‌های گیج اشغال نیم‌دایره.",
                "نوار ابزار اجرایی بالای داشبورد: گروه فیلتر بازه زمانی (امروز / این ماه / سال مالی ۱۴۰۵)، سوییچ زنده نمایش ارزی (ریال / لیر ₺) با تبدیل آنی کلاینت، و دکمه خروجی اکسل مدیریت انبار.",
                "ارتقاء ماتریس جامع موجودی (Navy Matrix): سوئیچ فیلتر اقلام دارای موجودی مثبت، فیلتر دراپ‌داون انبار با اتصال دوطرفه به گیج نیم‌دایره، و ستون عملیات سریع (کاردکس تعدادی، کاردکس ریالی، شارژ سریع PO).",
                "تفکیک شفاف ارزش ریالی موجودی ملکی شرکت در برابر کالای امانی در کارت طلایی شماره ۱."
            ],
            "🛡️ Security & Zero Ghost UI": [
                "اعمال گارد‌های دقیق دسترسی بر مایکرولینک‌های کارت ۳ و ۴ جهت جلوگیری قطعی از خطای ۴۰۳.",
                "بج‌های وضعیت و سلامت موجودی با رنگ‌های یکدست و کنتراست بالا (متن سفید #ffffff) و بدون عبارات ترکی در مود فارسی.",
                "پاس شدن ۱۰۰ درصدی آزمون ۴ لایه شکارچی باگ (Deep Bug Hunter) با صفر خطا."
            ]
        }
    },
    {
        "version": "3.2.1",
        "date": "۱۴۰۵/۰۷/۲۵ - 2026-10-16",
        "title": "پاکسازی کامل ۱۲۹ خطای ممیزی محیط توسعه (Zero IDE Problems) و تثبیت پایداری سیستم",
        "badge": "Previous Stable",
        "badge_color": "secondary",
        "categories": {
            "🚀 Architecture & Features": [
                "رفع کامل ۱۲۹ خطای سینتکس، اعتبارسنجی و لایه گزارش در تمپلیت‌های Jinja2 و محیط توسعه (Zero IDE Problems).",
                "تفکیک اسکریپت‌های چارت و نمودار با کانفیگ استاندارد application/json و حذف تداخل‌های مفسر جاوااسکریپت.",
                "پیکربندی خودکار و بهینه‌سازی موتور تحلیل Pylance و Pyright با ایجاد pyrightconfig.json و .vscode/settings.json جهت اتصال به venv پروژه."
            ],
            "🛡️ Security & RBAC Hardening": [
                "تثبیت ۱۰۰ درصدی آزمون ۴ لایه شکارچی باگ (Deep Bug Hunter) روی ۲۶ روت و ۵ نقش سازمانی با صفر باگ و صفر خطای ۵۰۰/۴۲۲.",
                "همگام‌سازی کامل پایگاه داده لوکال و سرور با پروتکل Zero Ghost UI."
            ]
        }
    },
    {
        "version": "3.2.0",
        "date": "۱۴۰۵/۰۷/۲۴ - 2026-10-15",
        "title": "داشبورد مدیریتی SaaS (الهام‌گرفته از FlowFin و Salezy) و ۴ ارتقاء سازمانی نوسا (Nosa ERP)",
        "badge": "Previous Stable",
        "badge_color": "secondary",
        "categories": {
            "🚀 Architecture & Features": [
                "بازطراحی کامل داشبورد مدیریتی با ۴ کارت شاخص کلیدی تصمیم‌گیری (ارزش دارایی، موجودی آزاد، خط لوله تامین و هشدارهای زنده) و هایپرلینک‌های دریل‌داون.",
                "ماتریس جامع دارایی و موجودی انبارها (Centerpiece Navy Matrix) با قابلیت جستجو، فیلتر انبار و میله پیشرفت نقطه سفارش.",
                "نمودارهای تحلیلی دوگانه سبک Salezy: مقایسه میله‌ای ورود و خروج کالا و گیج نیم‌دایره‌ای ظرفیت انبارها (70.8%).",
                "تفکیک و شخصی‌سازی آدرس و محل تخلیه/تحویل بار در سفارشات فروش (Delivery Address).",
                "پشتیبانی از تفکیک کالای ملکی شرکت از کالای امانی دیگران (Consignment vs. Owned) بدون اختلال در ارزیابی مالی دارایی‌ها.",
                "فرآیند بازرسی و تایید کنترل کیفیت (QC / Quarantine) در کارتابل پیش از ثبت قطعی موجودی."
            ],
            "🛡️ Security & RBAC Hardening": [
                "حفظ اصل Zero Ghost UI: مخفی‌سازی کامل ارزش مالی و سود ناخالص برای کاربران عملیاتی انبار و باسکول.",
                "هدایت هوشمند هایپرلینک‌های داشبورد بر اساس نقش کاربری جهت جلوگیری از خطای ۴۰۳."
            ],
            "⚖️ Financial & Tax Engine": [
                "محاسبه برخط و نمایش حاشیه سود ناخالص معاملات (Real-Time Gross Profit & Margin %) در جزئیات و لیست سفارشات فروش بر اساس بهای تمام‌شده میانگین موزون برای مدیران ارشد و مالی."
            ]
        }
    },
    {
        "version": "3.1.0",
        "date": "۱۴۰۵/۰۷/۲۴ - 2026-10-15",
        "title": "پروتکل محرمانگی مالی و جریان داده‌های بالادستی (Blind Warehouse & Top-Down Binding)",
        "badge": "Stable Release",
        "badge_color": "primary",
        "categories": {
            "🚀 Architecture & Features": [
                "پیاده‌سازی پروتکل محرمانگی مالی برای سرپرست انبار و اپراتور باسکول (Blind Inventory & Weighbridge).",
                "جریان اطلاعات از بالا به پایین: الصاق خودکار قیمت، طرف حساب و اطلاعات تکمیلی از سفارشات خرید (PO) و فروش (SO).",
                "افزایش پایداری تراکنش‌های سرور، کانکشن پولینگ pool_recycle=1800 و مدیریت امن خطاهای پایگاه‌داده."
            ],
            "🛡️ Security & RBAC Hardening": [
                "حذف کامل Ghost UI در تمامی فرم‌ها، جداول و منوهای سایدبار و هدر برای نقش‌های Warehouse و Baskool.",
                "مخفی‌سازی کامل مقادیر مالی (نرخ واحد، کرایه، بیمه و بهای تمام‌شده) در کاردکس، فرم تراکنش و قبوض باسکول برای رده‌های عملیاتی."
            ],
            "⚖️ Financial & Tax Engine": [
                "تطابق تقویم سیستم با سال مالی فعال ۱۴۰۵ و آماده‌سازی موتور انتقال قطعی مانده‌ها به سال مالی ۱۴۰۶.",
                "رفع قید خطای پایگاه‌داده برای ثبت اصلاحیه‌های ریالی و ممیزی هوشمند نرخ میانگین موزون."
            ]
        }
    },
    {
        "version": "3.0.0",
        "date": "۱۴۰۵/۰۷/۲۳ - 2026-10-14",
        "title": "بازطراحی رابط کاربری سازمانی (Accordion UI) و سامانه شکارچی خودکار باگ‌ها (/hunt)",
        "badge": "Major Release",
        "badge_color": "primary",
        "categories": {
            "🚀 Architecture & Features": [
                "طراحی مجدد رابط کاربری بر پایه منوی درختی تاشو (Accordion UI) سازمانی مطابق با استانداردهای SAP و سپیدار.",
                "طراحی و پیاده‌سازی اسکریپت شکارچی خودکار باگ‌ها (Deep Bug Hunter) با پوشش ۴ لایه تست عمیق.",
                "راه‌اندازی دستور یک‌کلمه‌ای و میانبر /hunt جهت ممیزی و خودترمیمی پیوسته سیستم."
            ],
            "🛡️ Security & RBAC Hardening": [
                "استانداردسازی و تفکیک قطعی وظایف (SoD) برای ۵ نقش کلیدی: Admin، Finance، Warehouse، Commercial و Baskool.",
                "دیوار امنیتی چندلایه در تمامی روترها و مسدودسازی دسترسی‌های غیرمجاز با پاسخ استاندارد ۴۰۳."
            ],
            "⚖️ Financial & Tax Engine": [
                "سازگاری کامل فرم‌ها با کیبورد و ارقام فارسی (۱۲۵.۵) و ممیز اعشاری ترکیه‌ای (125,5)."
            ]
        }
    },
    {
        "version": "2.5.0",
        "date": "۱۴۰۵/۰۶/۱۵ - 2026-09-05",
        "title": "درگاه واحد کارتابل انبار، رزرو موجودی فروش و اسناد اصلاحیه",
        "badge": "Feature Update",
        "badge_color": "info",
        "categories": {
            "🚀 Architecture & Features": [
                "پیاده‌سازی معماری درگاه واحد کارتابل انبار (Single Point of Entry) برای تمام تراکنش‌های ورودی و خروجی.",
                "رزرو هوشمند موجودی آزاد کالا (Available Stock) بلافاصله پس از ثبت سفارش فروش قبل از خروج فیزیکی بار.",
                "موتور اسناد اصلاحیه ریالی و مقداری و مرجوعی معکوس کالا با ردیابی سند والد."
            ],
            "🛡️ Security & RBAC Hardening": [
                "حفظ مانده کارتابل در صفحه‌بندی‌ها و جلوگیری از ناپدید شدن اسناد معلق با تفکیک کوئری پیجینیشن."
            ],
            "⚖️ Financial & Tax Engine": [
                "موتور بستن سال مالی با انتقال مانده‌های مثبت و حذف خودکار ردیف‌های صفر از اسناد افتتاحیه دوره جدید."
            ]
        }
    },
    {
        "version": "2.0.0",
        "date": "۱۴۰۵/۰۴/۰۱ - 2026-06-21",
        "title": "موتور دوارزی منطقه‌ای ایران/ترکیه، باسکول دیجیتال و کیسه‌گیری اوره",
        "badge": "Regional Engine",
        "badge_color": "warning",
        "categories": {
            "🚀 Architecture & Features": [
                "ماژول تخصصی باسکول تریلی در دو مرحله (توزین اول پر/خالی و توزین دوم متقابل) با اتصال به کارتابل انبار.",
                "عملیات صنعتی کیسه‌گیری و تبدیل اوره فله به جامبوبگ با موازنه دقیق جرم و بهای تمام‌شده بسته‌بندی.",
                "اعتبارسنجی پلاک‌های تریلی ایران و ترکیه و کنترل سقف تناژ راهداری (KGM)."
            ],
            "⚖️ Financial & Tax Engine": [
                "موتور مالیات دوارزی (IRR / TRY) با محاسبه خودکار مالیات بر ارزش افزوده (KDV) و نسبت توقیف مالیات آهن‌آلات (Tevkifat 4/10)."
            ]
        }
    },
    {
        "version": "1.0.0",
        "date": "۱۴۰۵/۰۱/۱۵ - 2026-04-04",
        "title": "هسته اولیه مدیریت انبار، کاتالوگ صنعتی متالورژی و کاردکس مقداری",
        "badge": "Initial Foundation",
        "badge_color": "secondary",
        "categories": {
            "🚀 Architecture & Features": [
                "هسته مرکزی انبارداری بر پایه FastAPI و SQLAlchemy با پشتیبانی از PostgreSQL و SQLite.",
                "کاتالوگ متالورژی آهن‌آلات و مقاطع فولادی با ویژگی‌های استاندارد، گرید، اشتال و واحد فرعی (شاخه/تن).",
                "کاردکس مقداری و ثبت تراکنش‌های رسید و حواله دستی انبار."
            ]
        }
    }
]


def load_release_history() -> List[Dict[str, Any]]:
    """بارگذاری سوابق انتشارات از فایل پویا یا استفاده از پیش‌فرض"""
    if os.path.exists(CHANGELOG_FILE):
        try:
            with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception as e:
            print(f"Error loading {CHANGELOG_FILE}: {e}")
    return DEFAULT_RELEASE_HISTORY


def save_release_history(history: List[Dict[str, Any]]):
    """ذخیره سوابق انتشارات در فایل JSON پایدار"""
    try:
        with open(CHANGELOG_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {CHANGELOG_FILE}: {e}")


def get_current_version() -> str:
    """دریافت آخرین نسخه ثبت‌شده سامانه"""
    history = load_release_history()
    if history:
        return history[0].get("version", CURRENT_VERSION)
    return CURRENT_VERSION


def bump_version(bump_type: str, title: str, changes: Dict[str, List[str]]) -> str:
    """
    افزایش خودکار نسخه سازمانی و درج یادداشت انتشار جدید
    bump_type: 'patch' (+0.0.1) | 'minor' (+0.1.0) | 'major' (+1.0.0)
    """
    history = load_release_history()
    current = get_current_version()
    parts = [int(p) for p in current.split(".")]
    while len(parts) < 3:
        parts.append(0)

    if bump_type.lower() == "major":
        parts[0] += 1
        parts[1] = 0
        parts[2] = 0
        badge = "Major Release"
        badge_color = "primary"
    elif bump_type.lower() == "minor":
        parts[1] += 1
        parts[2] = 0
        badge = "Feature Release"
        badge_color = "info"
    else:  # patch
        parts[2] += 1
        badge = "Maintenance Patch"
        badge_color = "success"

    new_version = ".".join(str(p) for p in parts)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    new_entry = {
        "version": new_version,
        "date": now_str,
        "title": title.strip(),
        "badge": badge,
        "badge_color": badge_color,
        "categories": changes
    }

    history.insert(0, new_entry)
    save_release_history(history)
    return new_version
