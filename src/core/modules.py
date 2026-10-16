"""
ماژول مرکزی مدیریت ماژول‌ها و سوئیچ‌های فیچر (Modular Architecture & Feature Flags)
امکان فعال‌سازی/غیرفعال‌سازی ماژول‌ها و کنترل تک‌ارزی/دوارزی از پنل مدیریت بدون نیاز به تغییر کد.
طراحی و مهندسی: امید پورمحمود (Omid Pourmahmoud)
سامانه: NexusPour Enterprise ERP
"""
import os
import json
from typing import Dict, Any
from fastapi import HTTPException, status

MODULES_CONFIG_FILE = "system_modules.json"

DEFAULT_MODULES: Dict[str, Any] = {
    "currency_mode": "ALL",       # "ALL" (دو ارزی ریال/لیر با سوئیچر) | "TR_ONLY" (فقط ترکیه/لیر) | "IR_ONLY" (فقط ایران/ریال)
    "module_weighbridge": True,    # باسکول دیجیتال تریلی
    "module_cutting": True,        # برشکاری و کارمزد آهن‌آلات / میلگرد / شمش
    "module_bagging": True,        # کیسه‌گیری اوره و کودهای شیمیایی
    "module_compliance": True,     # سامانه جامع تجارت (NTSW / صمت)
    "module_commercial": True,     # بازرگانی خرید و فروش (PO / SO)
}


def load_modules_config() -> Dict[str, Any]:
    """خواندن تنظیمات ماژول‌ها از فایل پیکربندی JSON با فال‌بک به پیش‌فرض‌ها"""
    if not os.path.exists(MODULES_CONFIG_FILE):
        save_modules_config(DEFAULT_MODULES)
        return DEFAULT_MODULES.copy()
    try:
        with open(MODULES_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # ترکیب با پیش‌فرض‌ها در صورت اضافه شدن کلید جدید
            for k, v in DEFAULT_MODULES.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    except Exception as e:
        print(f"[NexusPour Modules] Error loading config: {e}")
        return DEFAULT_MODULES.copy()


def save_modules_config(config: Dict[str, Any]) -> None:
    """ذخیره امن تنظیمات ماژول‌ها در فایل دیسک"""
    try:
        with open(MODULES_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[NexusPour Modules] Error saving config: {e}")


def is_module_enabled(module_name: str) -> bool:
    """بررسی فعال بودن یک ماژول مشخص در سامانه"""
    cfg = load_modules_config()
    key = f"module_{module_name}" if not module_name.startswith("module_") else module_name
    return bool(cfg.get(key, True))


def get_currency_mode() -> str:
    """دریافت حالت ارزی سامانه: ALL یا TR_ONLY یا IR_ONLY"""
    cfg = load_modules_config()
    return cfg.get("currency_mode", "ALL")


def check_module_access(module_name: str) -> None:
    """گارد اعتبارسنجی: در صورت غیرفعال بودن ماژول خطای ۴۰۳ صادر می‌شود"""
    if not is_module_enabled(module_name):
        module_titles = {
            "weighbridge": "باسکول دیجیتال تریلی",
            "cutting": "برشکاری و کارمزد آهن‌آلات",
            "bagging": "کیسه‌گیری و بسته‌بندی اوره",
            "compliance": "سامانه جامع تجارت و انبارها",
            "commercial": "سفارشات خرید و فروش (بازرگانی)"
        }
        title = module_titles.get(module_name, module_name)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"ماژول «{title}» توسط مدیر سیستم غیرفعال شده است."
        )
