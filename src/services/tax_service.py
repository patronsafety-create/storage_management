"""
NexusPour ERP - Turkish & Iranian Tax Engine (KDV & Demir-Çelik Tevkifatı)
Architect & Copyright: Omid Pourmahmoud
"""
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

@dataclass
class TaxCalculationResult:
    base_amount: float                  # مبلغ خالص پایه (Matrah)
    vat_rate: float                     # نرخ مالیات بر ارزش افزوده (مثلاً 0.20 یا 0.10)
    vat_amount: float                   # کل مالیات محاسبه‌شده (Hesaplanan KDV)
    has_tevkifat: bool                  # آیا مشمول توقیف مالیات آهن‌آلات است؟
    tevkifat_rate_str: Optional[str]    # نسبت توقیف به صورت متنی (مثلاً "4/10")
    tevkifat_numerator: int             # صورت کسر (مثلاً ۴)
    tevkifat_denominator: int           # مخرج کسر (مثلاً ۱۰)
    tevkifat_amount: float              # مبلغ توقیف‌شده متعلق به اداره مالیات (Tevkifat Tutarı)
    payable_vat: float                  # مالیات قابل پرداخت به فروشنده (Tahsil Edilecek KDV)
    total_payable: float                # کل مبلغ قابل پرداخت به فروشنده (Ödenecek Tutar / Genel Toplam)
    buyer_tax_liability: float          # تعهد مالیاتی خریدار به دولت از محل توقیف (KDV 2)
    currency_symbol: str                # نماد ارز (₺ یا ریال)
    region_code: str                    # کد کشور ("TR" یا "IR")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_amount": round(self.base_amount, 2),
            "vat_rate": round(self.vat_rate, 2),
            "vat_amount": round(self.vat_amount, 2),
            "has_tevkifat": self.has_tevkifat,
            "tevkifat_rate_str": self.tevkifat_rate_str,
            "tevkifat_amount": round(self.tevkifat_amount, 2),
            "payable_vat": round(self.payable_vat, 2),
            "total_payable": round(self.total_payable, 2),
            "buyer_tax_liability": round(self.buyer_tax_liability, 2),
            "currency_symbol": self.currency_symbol,
            "region_code": self.region_code
        }


class TaxService:
    # نرخ‌های استاندارد مالیات بر ارزش افزوده
    DEFAULT_VAT_RATE_IR = 0.10   # قانون مالیات بر ارزش افزوده ایران (۱۰٪)
    DEFAULT_VAT_RATE_TR = 0.20   # قانون مالیات بر ارزش افزوده عمومی ترکیه (Katma Değer Vergisi - %20 KDV)

    # نرخ‌های توقیف رسمی آهن و فولاد ترکیه (Tevkifat Oranları)
    TEVKIFAT_STEEL_STANDARD = "4/10"   # شمش، بیلت، میلگرد، لوله، پروفیل، کلاف فولادی
    TEVKIFAT_SCRAP_STANDARD = "5/10"   # ضایعات و قراضه آهن‌آلات

    @staticmethod
    def parse_tevkifat_ratio(ratio_str: Optional[str]) -> Tuple[int, int]:
        """تجزیه نسبت توقیف مانند '4/10' یا '5/10' به صورت و مخرج کسر"""
        if not ratio_str:
            return (0, 10)
        try:
            parts = ratio_str.strip().split("/")
            if len(parts) == 2:
                num = int(parts[0])
                den = int(parts[1])
                if den > 0:
                    return (num, den)
        except (ValueError, TypeError):
            pass
        return (0, 10)

    @classmethod
    def is_steel_tevkifat_eligible(
        cls,
        gtip_code: Optional[str] = None,
        category_code: Optional[str] = None,
        product_name: Optional[str] = None
    ) -> bool:
        """
        تشخیص مشمولیت کالا در نظام توقیف مالیاتی آهن و فولاد ترکیه (Demir-Çelik Tevkifatı)
        مطابق بخشنامه رسمی سازمان امور مالیاتی ترکیه (GİB):
        کالاهای فصل ۷۲ (آهن و فولاد) و فصل ۷۳ (محصولات و مصنوعات فولادی) مشمول توقیف ۴/۱۰ هستند.
        """
        # ۱. بررسی کد تعرفه گمرکی GTİP
        if gtip_code:
            clean_gtip = gtip_code.strip().replace(".", "")
            if clean_gtip.startswith("72") or clean_gtip.startswith("73"):
                return True

        # ۲. بررسی دسته‌بندی کالایی
        if category_code and category_code in ("STL-RAW", "STL-PIP", "STL-SHT"):
            return True

        # ۳. بررسی کلمات کلیدی فلزی و متالورژی
        if product_name:
            name_lower = product_name.lower()
            steel_keywords = (
                "demir", "çelik", "kütük", "nervürlü", "profil", "boru", "sac", "filmaşin",
                "rebar", "billet", "steel", "شمش", "میلگرد", "فولاد", "پروفیل", "لوله", "تیرآهن"
            )
            if any(kw in name_lower for kw in steel_keywords):
                # استثنا: مواد شیمیایی و اوره مشمول توقیف فولاد نیستند
                if "üre" in name_lower or "urea" in name_lower or "gübre" in name_lower or "اوره" in name_lower:
                    return False
                return True

        return False

    @classmethod
    def calculate_tax(
        cls,
        base_amount: float,
        region_code: str = "IR",
        is_steel: bool = False,
        custom_vat_rate: Optional[float] = None,
        tevkifat_ratio: Optional[str] = None,
        steel_base_amount: Optional[float] = None
    ) -> TaxCalculationResult:
        """
        محاسبه دقیق مالیات بر اساس قوانین کشور، تفکیک ارزش افزوده و سهم توقیف مالیاتی.
        در سفارشات ترکیبی (حاوی کالای فولادی و غیرفولادی)، توقیف فقط روی بخش فولادی اعمال می‌شود.
        """
        base = max(0.0, float(base_amount or 0.0))
        region = (region_code or "IR").upper().strip()

        if region == "TR":
            currency_symbol = "₺"
            vat_rate = custom_vat_rate if custom_vat_rate is not None else cls.DEFAULT_VAT_RATE_TR
            vat_amount = base * vat_rate

            # تعیین مبلغ پایه فولادی مشمول توقیف
            if steel_base_amount is not None:
                effective_steel_base = min(base, max(0.0, float(steel_base_amount)))
                apply_tevkifat = (effective_steel_base > 0)
            else:
                effective_steel_base = base if is_steel else 0.0
                apply_tevkifat = is_steel

            ratio_str = tevkifat_ratio if tevkifat_ratio else (cls.TEVKIFAT_STEEL_STANDARD if apply_tevkifat else None)

            if ratio_str and apply_tevkifat and effective_steel_base > 0:
                num, den = cls.parse_tevkifat_ratio(ratio_str)
                steel_vat = effective_steel_base * vat_rate
                tevkifat_amount = steel_vat * (num / den)
                payable_vat = vat_amount - tevkifat_amount
                total_payable = base + payable_vat
                buyer_liability = tevkifat_amount
                has_tevkifat = True
            else:
                num, den = 0, 10
                tevkifat_amount = 0.0
                payable_vat = vat_amount
                total_payable = base + vat_amount
                buyer_liability = 0.0
                has_tevkifat = False


            return TaxCalculationResult(
                base_amount=base,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                has_tevkifat=has_tevkifat,
                tevkifat_rate_str=ratio_str,
                tevkifat_numerator=num,
                tevkifat_denominator=den,
                tevkifat_amount=tevkifat_amount,
                payable_vat=payable_vat,
                total_payable=total_payable,
                buyer_tax_liability=buyer_liability,
                currency_symbol=currency_symbol,
                region_code=region
            )

        else:
            # نسخه ایران: مالیات بر ارزش افزوده استاندارد ۱۰٪ بدون توقیف
            currency_symbol = "ریال"
            vat_rate = custom_vat_rate if custom_vat_rate is not None else cls.DEFAULT_VAT_RATE_IR
            vat_amount = base * vat_rate
            total_payable = base + vat_amount

            return TaxCalculationResult(
                base_amount=base,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                has_tevkifat=False,
                tevkifat_rate_str=None,
                tevkifat_numerator=0,
                tevkifat_denominator=10,
                tevkifat_amount=0.0,
                payable_vat=vat_amount,
                total_payable=total_payable,
                buyer_tax_liability=0.0,
                currency_symbol=currency_symbol,
                region_code="IR"
            )
