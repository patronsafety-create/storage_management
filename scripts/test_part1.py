import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jinja2 import Environment, FileSystemLoader
from starlette.requests import Request
from src.core.localization.regions import (
    Region, REGIONS, get_active_region, get_translation, get_locale_dict
)

def make_request(cookie_region=None):
    headers = []
    if cookie_region:
        headers.append((b"cookie", f"nexus_region={cookie_region}".encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/login",
        "headers": headers,
    }
    return Request(scope)

def test_part1_localization():
    env = Environment(loader=FileSystemLoader("templates"))
    login_tmpl = env.get_template("login.html")
    base_tmpl = env.get_template("base.html")

    # ۱. تست تشخیص منطقه پیش‌فرض (ایران)
    req_default = make_request()
    reg_default = get_active_region(req_default)
    assert reg_default.code == "IR"
    print("Test 1 Passed: Default region is IR")

    # ۲. رندر صفحه لاگین برای ایران
    html_ir = login_tmpl.render(request=req_default, region=reg_default, error=None)
    assert 'نکسوس‌پـور' in html_ir
    assert 'ورود به سیستم' in html_ir
    assert 'dir="rtl"' in html_ir
    assert 'name="region" value="IR"' in html_ir
    print("Test 2 Passed: Login HTML for IR renders correctly in RTL and Persian")

    # ۳. تست تشخیص منطقه ترکیه از کوکی
    req_tr = make_request("TR")
    reg_tr = get_active_region(req_tr)
    assert reg_tr.code == "TR"
    print("Test 3 Passed: Region detected as TR from cookie")

    # ۴. رندر صفحه لاگین برای ترکیه
    html_tr = login_tmpl.render(request=req_tr, region=reg_tr, error=None)
    assert 'NexusPour' in html_tr
    assert 'Giriş Yap' in html_tr
    assert 'Kullanıcı Adı' in html_tr
    assert 'dir="ltr"' in html_tr
    assert 'name="region" value="TR"' in html_tr
    print("Test 4 Passed: Login HTML for TR renders correctly in LTR and Turkish")

    # ۵. رندر base.html برای ایران
    html_base_ir = base_tmpl.render(request=req_default, user=None)
    assert 'dir="rtl"' in html_base_ir
    assert 'نکسوس‌پـور' in html_base_ir
    assert 'IR' in html_base_ir
    print("Test 5 Passed: Base HTML for IR renders correctly in RTL and Persian")

    # ۶. رندر base.html برای ترکیه
    html_base_tr = base_tmpl.render(request=req_tr, user=None)
    assert 'dir="ltr"' in html_base_tr
    assert 'NexusPour' in html_base_tr
    assert 'TR' in html_base_tr
    assert 'Gösterge' in html_base_tr
    print("Test 6 Passed: Base HTML for TR renders correctly in LTR and Turkish")

    # ۷. تست دیکشنری‌های ترجمه
    assert get_translation("system.brand_subtitle", "fa") == "سامانه یکپارچه انبارداری و زنجیره تامین"
    assert get_translation("system.brand_subtitle", "tr") == "Entegre Depo Yönetim Sistemi ve Tedarik Zinciri ERP"
    assert get_translation("fields.gtip", "tr") == "GTİP Kodu (Gümrük)"
    assert get_translation("fields.tse_standard", "tr") == "TSE Kalite Standardı"
    print("Test 7 Passed: Translation dictionary resolution works flawlessly")

    print("\n>>> ALL PART 1 LOCALIZATION TESTS PASSED 100%! <<<")

if __name__ == "__main__":
    test_part1_localization()
