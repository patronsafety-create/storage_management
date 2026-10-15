# 🩺 کالبدشکافی و ممیزی فنی جامع سامانه نکسوس‌پـور (Full System Diagnostic)
> **سامانه یکپارچه انبارداری و زنجیره تأمین NexusPour ERP**  
> **مالکیت معنوی، طراحی و مهندسی:** امید پورمحمود (Omid Pourmahmoud)  
> **نسخه گزارش:** 2.5.0 Enterprise Diagnostic Audit  
> **وضعیت کدها:** دست‌نخورده و فریز شده (Freeze / Read-Only Audit)

---

## فهرست فصول گزارش
1. [کد کامل و کالبدشکافی صفحه داشبورد اصلی (Dashboard Audit)](#۱-کد-کامل-و-کالبدشکافی-صفحه-داشبورد-اصلی-dashboard-audit)
2. [نقشه کامل دسترسی‌ها و ماتریس تداخل‌ها (RBAC & Navigation Conflict Matrix)](#۲-نقشه-کامل-دسترسیها-و-ماتریس-تداخلها-rbac--navigation-conflict-matrix)
3. [لیست جامع باگ‌های کشف‌شده در سیستم (Self-Detected Bugs)](#۳-لیست-جامع-باگهای-کشفشده-در-سیستم-self-detected-bugs)
4. [نقشه درختی کامل فایل‌ها و روت‌های سامانه (Project Map)](#۴-نقشه-درختی-کامل-فایلها-و-روتهای-سامانه-project-map)
5. [کدهای فعلی توابع اصلی در فایل‌های کلیدی سیستم](#۵-کدهای-فعلی-توابع-اصلی-در-فایلهای-کلیدی-سیستم)
6. [طرح اصلاحی و نقشه راه پیشنهادی برای معمار سیستم (Architectural Remediation Plan)](#۶-طرح-اصلاحی-و-نقشه-راه-پیشنهادی-برای-معمار-سیستم-architectural-remediation-plan)

---

## ۱. کد کامل و کالبدشکافی صفحه داشبورد اصلی (Dashboard Audit)

### ۱.۱. کد کامل پایتون روت داشبورد در `src/api/ui.py`
روت داشبورد در فایل [src/api/ui.py](file:///c:/Users/opour/storage_management/src/api/ui.py) تعریف شده است:

```python
from fastapi import APIRouter, Request, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional

from src.core.dependencies import get_current_user
from src.infrastructure.database import get_db
from src.domain_model.inventory_models import StockTransaction, ProductCategory
from src.domain_model.auth_models import User
from src.domain_model.enums import DocumentStatus
from src.services.inventory_service import InventoryService
from src.core.localization.regions import localize_display_name, get_active_region

router = APIRouter(tags=["UI"], dependencies=[Depends(get_current_user)])
templates = Jinja2Templates(directory="templates")
templates.env.filters["tr_loc"] = localize_display_name


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    msg: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    transaction_count = db.query(StockTransaction).count()

    recent_transactions = (
        db.query(StockTransaction)
        .order_by(StockTransaction.created_at.desc())
        .limit(5)
        .all()
    )

    pending_transactions = (
        db.query(StockTransaction)
        .options(
            joinedload(StockTransaction.product),
            joinedload(StockTransaction.warehouse),
            joinedload(StockTransaction.supplier),
            joinedload(StockTransaction.customer),
            joinedload(StockTransaction.created_by)
        )
        .filter(StockTransaction.status == DocumentStatus.PENDING_APPROVAL)
        .order_by(StockTransaction.created_at.desc())
        .all()
    )

    is_admin = any(role.name == "Admin" for role in current_user.roles)

    # داده‌های نمودار: موجودی لحظه‌ای کالاها
    stock_balances = InventoryService.calculate_stock_balances(db)
    categories = db.query(ProductCategory).order_by(ProductCategory.name).all()

    active_region = get_active_region(request)
    is_tr = (active_region.code == "TR")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "tx_count": transaction_count,
            "recent_txs": recent_transactions,
            "pending_txs": pending_transactions,
            "msg": msg,
            "error": error,
            "user": current_user,
            "is_admin": is_admin,
            "stock_balances": stock_balances,
            "categories": categories,
            "active_region": active_region,
            "is_tr": is_tr,
        }
    )
```

---

### ۱.۲. ساختار و کد قالب `templates/dashboard.html`
فایل قالب [templates/dashboard.html](file:///c:/Users/opour/storage_management/templates/dashboard.html) دارای بخش‌های زیر است:

1. **نوار ابزار دکمه‌های سریع (Quick Actions):**
   - دکمه `ثبت تراکنش جدید` (`/inventory/transaction`) - بدون شرط نقش (نمایش به همه).
   - دکمه `گزارش موجودی` (`/inventory/balance`) - نمایش به همه.
   - دکمه `کاتالوگ کالاها` (`/master-data/products`) - نمایش به همه.
   - دکمه‌های مودال `تعریف کالا` و `تعریف انبار` - فقط `{% if is_admin %}`.
2. **باکس کارتابل زرد/قرمز اسناد در انتظار تأیید (`pending_txs`):**
   - شرط نمایش: `{% if pending_txs and pending_txs | length > 0 %}` (بدون فیلتر سطح دسترسی یا نقش کاربر!).
   - جدول شامل ستون‌های: `#`، `نوع سند`، `منبع سند`، `کالا`، `انبار`، `طرف تجاری`، `مقدار`، `شماره عطف/قبض`، `ثبت‌کننده`، و `اقدام انباردار`.
   - فرم تأیید نهایی: `POST /inventory/transactions/{{ pt.id }}/approve`.
   - فرم رد سند: `POST /inventory/transactions/{{ pt.id }}/reject` با مقدار پیش‌فرض هاردکدشده:
     `<input type="hidden" name="rejection_reason" value="رد از کارتابل پیشخوان">`.
3. **کارت‌های چهارگانه شاخص (Stat Cards):**
   - کارت ۱: `{{ tx_count }}` (اسناد تراکنش انبار)
   - کارت ۲: `{{ stock_balances | length }}` (اقلام ثبت‌شده در انبار)
   - کارت ۳: وضعیت دیتابیس (`فعال`)
   - کارت ۴: نقش کاربر: `{{ user.roles[0].name if user.roles else 'اپراتور' }}`
4. **بخش میانی دو ستونه:**
   - ستون راست (۵ از ۱۲): نمودار کیکی دونات Chart.js بر اساس موجودی‌های مثبت `stock_balances`.
   - ستون چپ (۷ از ۱۲): جدول ۵ تراکنش اخیر (`recent_txs`).
5. **مودال‌های تعریف کالا و انبار (مخصوص ادمین):**
   - فرم `POST /master-data/product` با فیلدهای سریع: `name`, `uom`, `sku`, `category_id`, `brand`.
   - فرم `POST /master-data/warehouse` با فیلد `name`.

---

### ۱.۳. تحلیل عیوب، باگ‌ها و تناقض‌های منطقی در صفحه داشبورد

| بخش داشبورد | متغیر / المان | کد فعلی | ایراد فنی و تناقض منطقی |
| :--- | :--- | :--- | :--- |
| **کارت آمار ۱** | `tx_count` | `db.query(StockTransaction).count()` | این کوئری **تمامی رکوردهای خام** جدول `stock_transactions` شامل اسناد معلق (`PENDING_APPROVAL`)، باطل‌شده (`CANCELLED`) و ردشده (`REJECTED`) را می‌شمارد. در نتیجه عدد نمایش‌داده‌شده با اسناد واقعی انبار مغایرت فاحش دارد. باید فقط اسناد `APPROVED` شمارش شوند. |
| **کارت آمار ۲** | `stock_balances \| length` | `len(InventoryService.calculate_stock_balances(db))` | تابع `calculate_stock_balances` یک `outerjoin` بین کالاها و انبارها می‌زند. این متغیر تعداد جفت‌های `(کالا، انبار)` حتی با موجودی **صفر** را برمی‌گرداند. اگر ۱۰ کالا در دیتابیس باشد که هیچ موجودی ندارند، عدد ۱۰ نمایش داده می‌شود، در حالی که کارت مدعی نمایش «اقلام موجود در انبار» است! |
| **کارت آمار ۴** | عنوان نقش | `user.roles[0].name` | الف) اگر کاربری چند نقش داشته باشد، ترتیب SQL تصادفی است. ب) نام انگلیسی پایگاه‌داده (مانند `Finance_Manager`, `Warehouse_Supervisor`, `Procurement_Officer`) مستقیماً بدون ترجمه فارسی به کاربر نمایش داده می‌شود. |
| **کارتابل اسناد معلق** | کل بلوک هشدار | `{% if pending_txs and pending_txs \| length > 0 %}` | **عدم وجود گارد نقش در تمپلیت:** این کارتابل به تمامی ۷ کاربر (شامل خریدار، فروشنده، اپراتور باسکول، مسئول کارگاه برش و مدیر مالی) نمایش داده می‌شود! |
| **دکمه تأیید کارتابل** | دکمه تایید سند | `form action="/inventory/transactions/{{ pt.id }}/approve"` | اگر کاربر خریدار (`buyer`) یا فروشنده (`seller`) یا باسکول (`baskool`) روی دکمه سبز تأیید کلیک کند، چون بک‌اند دارای قفل `require_roles(current_user, {"Admin", "Warehouse_Supervisor"})` است، سرور خطای **`403 Forbidden`** می‌دهد و صفحه سفید خطا ظاهر می‌شود! |
| **دکمه رد کارتابل** | فرم رد سند | `rejection_reason = "رد از کارتابل پیشخوان"` | برخلاف صفحه `transactions.html` که مودال باز کرده و دلیل رد را از انباردار می‌پرسد، در داشبورد یک مقدار هاردکدشده ارسال می‌شود و کاربر امکان ثبت علت واقعی کسری یا عدم تطابق را ندارد. |
| **جدول آخرین تراکنش‌ها** | `recent_transactions` | کوئری فاقد `joinedload` برای `product` و `warehouse` | الف) ایجاد خطای **N+1 Queries** در پایگاه‌داده. ب) نمایش تراکنش‌های در انتظار تأیید یا ردشده با برچسب سبز `ورود` یا قرمز `خروج` بدون نمایش وضعیت واقعی سند (`status`). |
| **دکمه‌های Quick Actions** | دکمه ثبت تراکنش | `<a href="/inventory/transaction">` | این دکمه به تمامی نقش‌ها نمایش داده می‌شود، در حالی که اپراتور باسکول، کارشناس خرید و کارشناس فروش طبق ماتریس نباید به ثبت سند دستی مستقیم دسترسی داشته باشند. |

---

## ۲. نقشه کامل دسترسی‌ها و ماتریس تداخل‌ها (RBAC & Navigation Conflict Matrix)

### ۲.۱. کد نحوه تعریف نقش‌ها و کاربران در دیتابیس (`src/infrastructure/seed_users.py`)
کد زیر نحوه مقداردهی اولیه ۷ نقش و کاربر سازمانی سامانه با پسورد پیش‌فرض `1234` را در [src/infrastructure/seed_users.py](file:///c:/Users/opour/storage_management/src/infrastructure/seed_users.py) نشان می‌دهد:

```python
TEST_USERS_DATA = [
    {
        "username": "admin",
        "full_name": "مدیر ارشد سیستم (امید پورمحمود)",
        "role_name": "Admin",
        "role_desc": "مدیر کل و معمار ارشد سیستم - دسترسی کامل به تمامی بخش‌ها"
    },
    {
        "username": "finance",
        "full_name": "مدیر مالی و حسابرسی",
        "role_name": "Finance_Manager",
        "role_desc": "مدیریت حسابداری، کاردکس ریالی، اصلاحیه‌ها، بستن سال مالی، گزارشات مالی خرید و فروش"
    },
    {
        "username": "warehouse",
        "full_name": "سرپرست انبار مرکزی",
        "role_name": "Warehouse_Supervisor",
        "role_desc": "کارتابل تأیید اسناد انبار، موجودی لحظه‌ای، حواله انتقال، انبارگردانی، مرجوعی کالا"
    },
    {
        "username": "buyer",
        "full_name": "کارشناس بازرگانی خرید",
        "role_name": "Procurement_Officer",
        "role_desc": "مدیریت تأمین‌کنندگان، ثبت سفارشات خرید (PO) و پیگیری ورود بار"
    },
    {
        "username": "seller",
        "full_name": "کارشناس بازرگانی فروش",
        "role_name": "Sales_Officer",
        "role_desc": "مدیریت مشتریان، صدور پیش‌فاکتور و سفارشات فروش (SO) و حواله تحویل"
    },
    {
        "username": "baskool",
        "full_name": "اپراتور باسکول دیجیتال",
        "role_name": "Weighbridge_Operator",
        "role_desc": "عملیات توزین اول و دوم ناوگان سنگین و ثبت قبوض باسکول"
    },
    {
        "username": "workshop",
        "full_name": "مسئول کارگاه برش و کیسه‌گیری",
        "role_name": "Production_Operator",
        "role_desc": "دستورات برش آهن و پروفیل، مدیریت ته‌شاخه و کیسه‌گیری فله اوره"
    }
]
```

---

### ۲.۲. توابع بررسی دسترسی در بک‌اند
۱. تابع استخراج کاربر جاری و توکن JWT در [src/core/dependencies.py](file:///c:/Users/opour/storage_management/src/core/dependencies.py):
```python
async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        if token.startswith("Bearer "):
            token = token.split(" ")[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token verification failed")

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or disabled")
    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not any(role.name == "Admin" for role in current_user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی غیرمجاز. این عملیات فقط برای مدیر کل سیستم امکان‌پذیر است.")
    return current_user
```

۲. گارد چندنقشی `require_roles` در [src/api/inventory_ui.py](file:///c:/Users/opour/storage_management/src/api/inventory_ui.py#L39-L49):
```python
def require_roles(user: User, allowed_roles: set[str], action_desc: str = ""):
    user_roles = {r.name for r in getattr(user, "roles", [])}
    if not user_roles.intersection(allowed_roles):
        raise HTTPException(
            status_code=403,
            detail="عدم دسترسی به این عملیات / Bu işlem için yetkiniz bulunmamaktadır"
        )
```

---

### ۲.۳. کدهای منوی سایدبار و نوبار در `templates/base.html`
در [templates/base.html](file:///c:/Users/opour/storage_management/templates/base.html#L557-L692) نقش‌ها به صورت زیر استخراج و فیلتر می‌شوند:

```jinja2
  {% if user %}
    {% set user_role_names = user.roles | map(attribute='name') | list %}
    {% set is_admin = ('Admin' in user_role_names) or (user.username == 'admin') %}
    {% set is_finance = ('Finance_Manager' in user_role_names) or (user.username == 'finance') %}
    {% set is_warehouse = ('Warehouse_Supervisor' in user_role_names) or (user.username == 'warehouse') %}
    {% set is_buyer = ('Procurement_Officer' in user_role_names) or (user.username == 'buyer') %}
    {% set is_seller = ('Sales_Officer' in user_role_names) or (user.username == 'seller') %}
    {% set is_baskool = ('Weighbridge_Operator' in user_role_names) or (user.username == 'baskool') %}
    {% set is_workshop = ('Production_Operator' in user_role_names) or (user.username == 'workshop') %}
  {% endif %}
```

و نمایش آیتم‌های سایدبار:
```jinja2
  <!-- پیشخوان و وضعیت -->
  <a href="/dashboard">داشبورد و نمودار کیکی</a>
  {% if is_admin or is_warehouse or is_finance or is_buyer or is_seller or is_workshop %}
  <a href="/inventory/balance">گزارش موجودی لحظه‌ای</a>
  <a href="/inventory/transactions">لیست و جستجوی تراکنش‌ها</a>
  {% endif %}

  <!-- تعاریف پایه و کاتالوگ -->
  {% if is_admin or is_finance or is_warehouse or is_buyer or is_seller %}
  <a href="/master-data/products">کاتالوگ و مدیریت کالاها</a>
  <a href="/master-data/parties">طرف‌های تجاری (تأمین‌کننده / مشتری)</a>
  {% endif %}

  <!-- عملیات انبارداری و زنجیره تأمین -->
  {% if is_admin or is_warehouse or is_finance %}
  <a href="/inventory/transaction">ثبت رسید / حواله انبار</a>
  {% endif %}
  {% if is_admin or is_finance or is_buyer %}
  <a href="/purchases">سفارشات خرید و رسید کالا (PO)</a>
  {% endif %}
  {% if is_admin or is_finance or is_seller %}
  <a href="/sales">سفارشات فروش و حواله کالا (SO)</a>
  {% endif %}
  {% if is_admin or is_baskool or is_warehouse %}
  <a href="/weighbridge">باسکول دیجیتال تریلی و قبض</a>
  {% endif %}
  {% if is_admin or is_workshop %}
  <a href="/cutting">دستور برش و انبار ته‌شاخه آهن</a>
  <a href="/bagging">کیسه‌گیری فله به جامبوبگ اوره</a>
  {% endif %}
  {% if is_admin or is_warehouse %}
  <a href="/inventory/transfer">انتقال بین انبارها</a>
  <a href="/inventory/stocktaking">انبارگردانی و مغایرت‌گیری</a>
  {% endif %}
  {% if is_admin or is_warehouse or is_finance %}
  <a href="/inventory/returns/new">برگشت از خرید / برگشت از فروش</a>
  {% endif %}
  {% if is_admin or is_finance %}
  <a href="/inventory/fiscal-years">سال مالی و بستن دوره</a>
  {% endif %}
```

---

### ۲.۴. ماتریس کامل تداخل‌های دسترسی (Backend Route Guard vs Frontend UI Visibility)

در جدول زیر، وضعیت واقعی کنترل دسترسی در کد پایتون سمت سرور (Backend) با وضعیت نمایش دکمه‌ها و لینک‌ها در قالب‌های HTML مقایسه شده و تداخل‌ها (**CONFLICT**) مشخص شده‌اند:

| مسیر (URL Route) | متد | دسترسی مجاز طبق مستندات (`ROADMAP`) | محافظت واقعی در بک‌اند (Python) | چه نقش‌هایی در HTML دکمه/لینک را می‌بینند؟ | نوع تداخل و مغایرت امنیتی / فرآیندی |
| :--- | :---: | :--- | :--- | :--- | :--- |
| `/dashboard` | GET | همه نقش‌ها | فقط لاگین (`get_current_user`) | همه نقش‌ها | **تداخل فرآیندی:** کارتابل تأیید اسناد معلق و دکمه‌های تأیید/رد به همه نقش‌ها نشان داده می‌شود در حالی که کلیک روی آن خطای 403 می‌دهد. |
| `/inventory/transaction` | GET / POST | `Admin`, `Finance`, `Warehouse` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | در سایدبار: Admin, Finance, Warehouse.<br>در داشبورد: **همه کاربران!** | **رخنه امنیتی و تداخل:** کارشناس خرید (`buyer`) و فروش (`seller`) و باسکول می‌توانند با زدن دکمه روی داشبورد یا وارد کردن مستقیم URL، سند ورود/خروج دستی صادر کنند! |
| `/inventory/transactions` | GET | `Admin`, `Finance`, `Warehouse` | **هیچ کنترلی وجود ندارد!** | Admin, Finance, Warehouse, Buyer, Seller, Workshop | **تداخل UI:** خریدار، فروشنده و کارگاه نباید کارتابل اسناد انبار را ببینند اما در سایدبار به آنها نشان داده می‌شود. |
| `/inventory/transactions/{id}/approve` | POST | `Admin`, `Warehouse` | قفل دارد: `require_roles(Admin, Warehouse_Supervisor)` | در داشبورد به **تمامی کاربران** نشان داده می‌شود! | **تداخل شدید (UI Crash):** هر کاربری جز انباردار دکمه را بزند با خطای 403 مسدود می‌شود. |
| `/inventory/transactions/{id}/reject` | POST | `Admin`, `Warehouse` | قفل دارد: `require_roles(Admin, Warehouse_Supervisor)` | در داشبورد به **تمامی کاربران** نشان داده می‌شود! | **تداخل شدید:** خطای 403 برای کاربران غیر انباردار. |
| `/inventory/transactions/{id}/adjust` | POST | `Admin`, `Finance` | قفل دارد: `require_roles(Admin, Finance_Manager)` | در تمپلیت تراکنش‌ها | همخوانی دارد. |
| `/purchases` | GET / POST | `Admin`, `Finance`, `Buyer` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Finance, Buyer | **رخنه امنیتی:** کارشناس فروش (`seller`) یا باسکول (`baskool`) با باز کردن `/purchases` در آدرس‌بار می‌توانند سفارشات خرید را ببینند یا سفارش جدید ایجاد کنند! |
| `/purchases/{id}/receive` | POST | `Admin`, `Buyer`, `Warehouse` | **هیچ کنترلی وجود ندارد!** | هر کاربری که وارد صفحه سفارش خرید شود | **رخنه امنیتی:** هر کاربری می‌تواند بارنامه سفارش خرید را به کارتابل انبار بفرستد. |
| `/sales` | GET / POST | `Admin`, `Finance`, `Seller` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Finance, Seller | **رخنه امنیتی:** خریدار یا باسکول با آدرس مستقیم می‌توانند به سفارشات فروش و قیمت‌ها دسترسی پیدا کنند. |
| `/sales/{id}/deliver` | POST | `Admin`, `Seller`, `Warehouse` | **هیچ کنترلی وجود ندارد!** | هر کاربری در صفحه جزئیات فروش | هر کاربری می‌تواند حواله خروج کالا صادر کند. |
| `/weighbridge` | GET / POST | `Admin`, `Baskool` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Baskool, **Warehouse** | **تداخل دوگانه:** ۱) انباردار نباید باسکول را ببیند اما در سایدبار دارد. ۲) در بک‌اند هیچ کاربری محدود نشده است. |
| `/weighbridge/{id}/complete` | POST | `Admin`, `Baskool` | **هیچ کنترلی وجود ندارد!** | اپراتور در صفحه توزین دوم | عدم احراز هویت نقش اپراتور باسکول. |
| `/cutting` | GET / POST | `Admin`, `Workshop` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Workshop | در صورت وارد کردن مستقیم آدرس، کاربران دیگر هم می‌توانند دستور برش ثبت کنند. |
| `/bagging` | GET / POST | `Admin`, `Workshop` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Workshop | فاقد قفل بک‌اند. |
| `/inventory/transfer` | GET / POST | `Admin`, `Warehouse` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Warehouse | فاقد قفل بک‌اند. |
| `/inventory/stocktaking` | GET / POST | `Admin`, `Warehouse` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Warehouse | فاقد قفل بک‌اند. |
| `/inventory/fiscal-years` | GET | `Admin`, `Finance` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | Admin, Finance | فاقد قفل بک‌اند. |
| `/inventory/fiscal-year-close` | GET / POST | `Admin`, `Finance` | قفل دارد: `require_roles(Admin, Finance_Manager)` | Admin, Finance | همخوانی دارد. |
| `/master-data/supplier` | POST | `Admin`, `Buyer` | **فقط `require_admin`!** | در HTML فقط به `Admin` دکمه داده شده | **تداخل شدید کاری:** کارشناس بازرگانی خرید (`buyer`) که وظیفه سازمانی‌اش تأمین‌کنندگان است، **نمی‌تواند تأمین‌کننده جدید ثبت یا ویرایش کند**! |
| `/master-data/customer` | POST | `Admin`, `Seller` | **فقط `require_admin`!** | در HTML فقط به `Admin` دکمه داده شده | **تداخل شدید کاری:** کارشناس بازرگانی فروش (`seller`) که باید مشتری تعریف کند، **دسترسی ثبت مشتری ندارد**! |
| `/admin/audit-logs` | GET | فقط `Admin` | **هیچ کنترلی وجود ندارد!** (فقط لاگین) | فقط `Admin` در منو می‌بیند | **آسیب‌پذیری افشای اطلاعات (Information Disclosure):** هر کاربری با نوشتن `/admin/audit-logs` می‌تواند لاگ‌های محرمانه امنیتی را بخواند! |
| `/admin/users` | GET / POST | فقط `Admin` | قفل دارد: `Depends(require_admin)` | فقط Admin | همخوانی دارد. |

---

## ۳. لیست جامع باگ‌های کشف‌شده در سیستم (Self-Detected Bugs)

### ۳.۱. دسته الف: باگ‌های ظاهری و قالب‌ها (UI / Jinja2 Templates)

1. **باگ صفحه تراکنش‌ها (`templates/transactions.html` L27-L32): حذف اسناد کارتابل در صورت صفحه‌بندی**
   - در کد تمپلیت نوشته شده:
     ```jinja2
     {% set pending_txs = [] %}
     {% for t in transactions %}
       {% if t.status and t.status.value == 'PENDING_APPROVAL' %}
         {% set _ = pending_txs.append(t) %}
       {% endif %}
     {% endfor %}
     ```
   - **علت و اثر باگ:** متغیر `transactions` فقط ۱۰ ردیف صفحه‌بندی‌شده صفحه جاری را در بر دارد. اگر سند معلقی در صفحه ۲ یا ۳ باشد یا کاربر فیلتر کالا بگذارد، سند از کارتابل بالای صفحه **ناپدید می‌شود**! بک‌اند باید `pending_txs` را جداگانه مانند `ui.py` کوئری بزند و ارسال کند.
2. **باگ داشبورد: عدم امکان ثبت دلیل رد سند در کارتابل پیشخوان**
   - در `dashboard.html` دلیل رد به صورت پیش‌فرض هاردکد است:
     `<input type="hidden" name="rejection_reason" value="رد از کارتابل پیشخوان">`
   - انباردار نمی‌تواند دلیل فنی رد سند (مانند کسری بار، خرابی، عدم انطباق با بارنامه) را مشخص کند.
3. **باگ تداخل دکمه‌های اقدام کارتابل در داشبورد برای سایر نقش‌ها**
   - عدم قرارگیری شرط `{% if is_admin or is_warehouse %}` دور دکمه‌های اقدام و کارتابل داشبورد، که باعث پرتاب خطای ۴۰۳ می‌شود.
4. **باگ عدم تفکیک مبالغ ریالی و لیری در کارت‌های آماری**
   - در صورت استفاده از حالت دو ارزی (IRR و TRY)، جمع جبری مستقیم در کارت‌ها انجام می‌شود بدون این که ارز مشخص باشد.

---

### ۳.۲. دسته ب: باگ‌های فرآیندی و منطقی (Workflow & Business Logic)

1. **باگ چرخه باسکول و خرید: خطر صدور سند مضاعف (Double Transaction Cartable)**
   - در `weighbridge_ui.py` خطوط ۳۴۰ تا ۳۷۵: اگر اپراتور باسکول توزین دوم را قبل از کلیک روی «تخلیه و ارسال به کارتابل انبار» در صفحه سفارش خرید انجام دهد، باسکول یک سند معلق جدید می‌سازد. سپس وقتی مسئول خرید دکمه «ارسال به کارتابل» را در `/purchases/{id}/receive` می‌زند، **یک سند معلق دوم برای همان بار** صادر می‌شود و انباردار دو بار سند دریافت می‌کند!
2. **باگ تبدیل واحد باسکول برای اقلام شاخه‌ای و عددی (UOM Mismatch)**
   - در `weighbridge_ui.py` خطوط ۳۱۴-۳۱۶:
     ```python
     is_ton = ticket.product and ticket.product.uom in ("تن", "Ton", "ton")
     net_qty = (ticket.net_weight / 1000.0) if is_ton else ticket.net_weight
     ```
   - اگر کالایی واحدش «شاخه» باشد، کد فرض می‌کند که باید مستقیماً کیلوگرم را در فیلد مقدار بنشاند! مثلاً تریلی حامل ۲۴,۰۰۰ کیلوگرم میلگرد به عنوان **۲۴,۰۰۰ شاخه** در سند انبار ثبت می‌شود نه بر مبنای وزن هر شاخه (`nominal_weight`)!
3. **کنترل سقف اعتبار مالی مشتری بدون لحاظ بدهی‌های قبلی**
   - در `sales_ui.py` خطوط ۲۸۸-۲۹۵: کد فقط مبلغ سفارش جاری `so.total_amount` را با `customer.credit_limit` مقایسه می‌کند و مانده‌حساب و مطالبات قبلی مشتری از فاکتورهای گذشته بررسی نمی‌شود.
4. **تناقض چرخه تأیید کارگاه برش و کیسه‌گیری با کارتابل انبار**
   - اسناد حاصل از برش تیرآهن و کیسه‌گیری اوره مستقیماً با وضعیت `APPROVED` ثبت و وارد موجودی قطعی می‌شوند، در حالی که اسناد خرید، فروش و باسکول وارد کارتابل `PENDING_APPROVAL` می‌شوند. این امر باعث ناهماهنگی در کنترل انبار مرکزی می‌گردد.

---

### ۳.۳. دسته ج: باگ‌های امنیتی و دسترسی (Security & Permissions)

1. **آسیب‌پذیری افشای لاگ‌های امنیتی (`/admin/audit-logs`)**
   - روت لاگ‌های سیستم در [src/api/audit_ui.py](file:///c:/Users/opour/storage_management/src/api/audit_ui.py) دارای پیشوند `/admin` است، اما هیچ گارد `require_admin` ندارد. هر کاربری با هر نقشی (حتی اپراتور ساده) می‌تواند تمام ردپای تغییرات و IPهای کاربران را مشاهده کند.
2. **قفل شدن کارشناس خرید (`buyer`) در تعریف تأمین‌کننده**
   - روت‌های `POST /master-data/supplier` و ویرایش آن فقط برای نقش `Admin` مجاز است (`Depends(require_admin)`). کارشناس خرید نمی‌تواند کارخانه یا بنگاه جدید ثبت کند.
3. **قفل شدن کارشناس فروش (`seller`) در تعریف مشتری**
   - روت‌های `POST /master-data/customer` و ویرایش آن فقط به `Admin` اختصاص یافته است.
4. **فقدان گارد نقش در تمام روت‌های حساس فرآیندی**
   - تمامی روت‌های ثبت سفارش خرید، صدور سفارش فروش، تکمیل قبض باسکول، دستور برش، کیسه‌گیری، انتقال و انبارگردانی فاقد گارد نقش هستند و تنها احراز هویت ساده دارند.

---

## ۴. نقشه درختی کامل فایل‌ها و روت‌های سامانه (Project Map)

### ۴.۱. درخت فایل‌های پایتون بک‌اند (`src/`)
```text
c:\Users\opour\storage_management\src\
├── __init__.py
├── schemas.py
├── requirements.txt
├── api/
│   ├── admin_ui.py              # مدیریت کاربران و تخصیص نقش‌ها
│   ├── alerts_ui.py             # مرکز هشدارهای نقطه سفارش و وب‌سرویس بچ
│   ├── audit_ui.py              # لاگ جامع حسابرسی و ردپای امنیتی
│   ├── auth.py                  # ورود، خروج، سشن کوکی، سوئیچ زبان IR/TR
│   ├── bagging_ui.py            # زیرسیستم کیسه‌گیری فله اوره به جامبوبگ
│   ├── compliance_ui.py         # انطباق سامانه تجارت و خروجی اکسل NTSW
│   ├── cutting_ui.py            # دستور برش تیرآهن، میلگرد و ته‌شاخه
│   ├── dependencies.py          # احراز هویت Bearer Token برای Swagger
│   ├── inventory_ui.py          # موتور جامع انبارداری، کاردکس، کارتابل، بستن سال مالی
│   ├── main.py                  # پیکربندی FastAPI، میدل‌ویر نرمال‌سازی و روترها
│   ├── master_data_ui.py        # کاتالوگ کالاها، انبارها، رده‌ها
│   ├── parties_ui.py            # طرف‌های تجاری (تأمین‌کنندگان و مشتریان)
│   ├── purchases_ui.py          # سفارشات خرید (PO) و محاسبه مالیات و توقیف
│   ├── sales_ui.py              # سفارشات فروش (SO) و حواله خروج
│   ├── stock_api.py             # وب‌سرویس REST موجودی انبار
│   ├── ui.py                    # پیشخوان داشبورد و راهنمای جامع کاربری
│   └── weighbridge_ui.py        # باسکول دیجیتال و توزین اول/دوم
├── core/
│   ├── dependencies.py          # گاردهای امنیتی (get_current_user, require_admin)
│   └── localization/
│       ├── __init__.py
│       ├── regions.py           # فیلترهای Jinja2، تقویم جلالی/میلادی، ارزها
│       └── tr_rules.py          # اعتبارسنجی VKN، پلاک ترکیه، سقف تناژ KGM
├── domain_model/
│   ├── auth_models.py           # مدل‌های User و Role
│   ├── auth_schemas.py          # اسکیمای توکن و سشن
│   ├── enums.py                 # وضعیت اسناد، نوع تراکنش، منابع سفارش
│   ├── inventory_models.py      # مدل‌های جامع کالا، تراکنش، باسکول، برش، کیسه و سال مالی
│   ├── models.py
│   └── user_models.py
├── infrastructure/
│   ├── database.py              # اتصال موتور SQLAlchemy به PostgreSQL/SQLite
│   ├── number_normalizer.py     # میدل‌ویر نرمال‌سازی ارقام فارسی/عربی و اعشار ترکی
│   ├── security.py              # توابع هش Argon2 و ساخت توکن JWT
│   └── seed_users.py            # ایجاد خودکار ۷ نقش و کاربر تستی سازمانی
└── services/
    ├── audit_service.py         # سرویس ثبت رویدادها در audit_logs
    ├── inventory_service.py     # محاسبات موجودی، کاردکس، نرخ موزون و سال مالی
    └── tax_service.py           # موتور مالیات ارزش‌افزوده (KDV) و توقیف آهن (Tevkifat)
```

---

### ۴.۲. درخت فایل‌های قالب HTML (`templates/`)
```text
c:\Users\opour\storage_management\templates\
├── base.html                    # قالب مادر، نوبار، سایدبار، اسکریپت تقویم و ارقام
├── login.html                   # صفحه ورود با منوی انتخاب سریع کاربران تستی
├── dashboard.html               # پیشخوان، نمودار دونات، آمار و کارتابل
├── user_guide.html              # راهنمای جامع و کاتالوگ کاربری
├── products.html                # کاتالوگ کالاها، پارامترهای فنی و متالورژی
├── barcode_label.html           # چاپ لیبل بارکد و QR Code استاندارد
├── parties.html                 # طرف‌های تجاری (تأمین‌کننده و مشتری)
├── transactions.html            # تاریخچه تراکنش‌ها و کارتابل اسناد معلق
├── transaction_form.html        # فرم ثبت رسید و حواله مستقیم با دو واحد و بهای تمام‌شده
├── print_voucher.html           # برگه چاپی رسمی سند انبار
├── stock_balance.html           # گزارش موجودی لحظه‌ای و دو واحدی
├── kardex.html                  # کاردکس مقداری کالا
├── financial_kardex.html        # کاردکس ریالی با میانگین موزون و اصلاحیه
├── transfer_form.html           # فرم حواله انتقال بین انبارها
├── stocktaking.html             # فرم انبارگردانی و ثبت شمارش عینی
├── stocktaking_blind_sheet.html # برگه پرینت شمارش کور انبارگردانی
├── return_form.html             # فرم ثبت برگشت از خرید و برگشت از فروش
├── fiscal_years.html            # مدیریت سال‌های مالی
├── fiscal_close.html            # فرم پیش‌نمایش و بستن سال مالی
├── purchases.html               # داشبورد سفارشات خرید (PO)
├── purchase_form.html           # فرم صدور سفارش خرید با توقیف مالیاتی
├── purchase_detail.html         # جزئیات سفارش خرید و دکمه ارسال به کارتابل
├── sales.html                   # داشبورد سفارشات فروش (SO)
├── sales_form.html              # فرم صدور سفارش فروش
├── sales_detail.html            # جزئیات سفارش فروش و دکمه صدور حواله خروج
├── weighbridge.html             # داشبورد باسکول و قبوض فعال
├── weighbridge_form.html        # فرم ثبت نوبت توزین اول باسکول
├── weighbridge_second_form.html # فرم ثبت توزین دوم باسکول
├── weighbridge_slip.html        # قبض رسمی پرینت باسکول دیجیتال
├── cutting.html                 # لیست دستورات برش آهن و ته‌شاخه‌ها
├── cutting_form.html            # فرم ثبت دستور برش و انتقال ته‌شاخه
├── bagging.html                 # مانیتورینگ کیسه‌گیری فله به جامبوبگ اوره
├── bagging_form.html            # فرم ثبت کیسه‌گیری فله
├── alerts.html                  # مرکز هشدارهای نقطه سفارش و راکد
├── compliance.html              # داشبورد انطباق با سامانه‌های دولتی و تجارت
├── audit_logs.html              # گزارش ردپای امنیتی و لاگ حسابرسی
├── users.html                   # مدیریت کاربران و نقش‌ها
├── mtc_certificate.html         # گواهینامه متالورژی MTC کالا
└── error.html                   # صفحه نمایش خطاهای سیستمی
```

---

### ۴.۳. جدول جامع تمام روت‌های فعال پروژه و سطح دسترسی کنونی

| ردیف | روت کامل (Endpoint) | متد | روتر مبدأ | دسترسی مورد انتظار | محافظت اعمال‌شده فعلی در کد |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **۱** | `/login` | GET / POST | `auth.py` | عمومی | عمومی |
| **۲** | `/logout` | GET | `auth.py` | لاگین‌شده | لاگین‌شده |
| **۳** | `/set-region/{region_code}` | GET | `auth.py` | عمومی | عمومی |
| **۴** | `/dashboard` | GET | `ui.py` | لاگین‌شده | لاگین‌شده |
| **۵** | `/guide` | GET | `ui.py` | لاگین‌شده | لاگین‌شده |
| **۶** | `/inventory/transaction` | GET / POST | `inventory_ui.py` | `Admin`, `Finance`, `Warehouse` | **فاقد قفل نقش** |
| **۷** | `/inventory/balance` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۸** | `/inventory/transactions` | GET | `inventory_ui.py` | `Admin`, `Finance`, `Warehouse` | **فاقد قفل نقش** |
| **۹** | `/inventory/kardex/{product_id}` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۱۰** | `/inventory/transfer` | GET / POST | `inventory_ui.py` | `Admin`, `Warehouse` | **فاقد قفل نقش** |
| **۱۱** | `/inventory/stocktaking` | GET / POST | `inventory_ui.py` | `Admin`, `Warehouse` | **فاقد قفل نقش** |
| **۱۲** | `/inventory/stocktaking/blind-sheet` | GET | `inventory_ui.py` | `Admin`, `Warehouse` | **فاقد قفل نقش** |
| **۱۳** | `/inventory/financial-kardex/{product_id}` | GET | `inventory_ui.py` | `Admin`, `Finance` | **فاقد قفل نقش** |
| **۱۴** | `/inventory/transaction/{tx_id}/print` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۱۵** | `/inventory/export/stock` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۱۶** | `/inventory/export/transactions` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۱۷** | `/inventory/transactions/{tx_id}/approve` | POST | `inventory_ui.py` | `Admin`, `Warehouse` | `require_roles(Admin, Warehouse_Supervisor)` |
| **۱۸** | `/inventory/transactions/{tx_id}/reject` | POST | `inventory_ui.py` | `Admin`, `Warehouse` | `require_roles(Admin, Warehouse_Supervisor)` |
| **۱۹** | `/inventory/transactions/{tx_id}/cancel` | POST | `inventory_ui.py` | `Admin`, `Warehouse` | `require_roles(Admin, Warehouse_Supervisor)` |
| **۲۰** | `/inventory/transactions/{tx_id}/adjust` | POST | `inventory_ui.py` | `Admin`, `Finance` | `require_roles(Admin, Finance_Manager)` |
| **۲۱** | `/inventory/fiscal-years` | GET | `inventory_ui.py` | `Admin`, `Finance` | **فاقد قفل نقش** |
| **۲۲** | `/inventory/fiscal-year-close` | GET / POST | `inventory_ui.py` | `Admin`, `Finance` | `require_roles(Admin, Finance_Manager)` |
| **۲۳** | `/inventory/returns/new` | GET | `inventory_ui.py` | `Admin`, `Warehouse`, `Finance` | **فاقد قفل نقش** |
| **۲۴** | `/inventory/returns` | POST | `inventory_ui.py` | `Admin`, `Warehouse`, `Finance` | **فاقد قفل نقش** |
| **۲۵** | `/inventory/transactions/{tx_id}/mtc` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۲۶** | `/inventory/products/{product_id}/label` | GET | `inventory_ui.py` | لاگین‌شده | لاگین‌شده |
| **۲۷** | `/purchases` | GET / POST | `purchases_ui.py` | `Admin`, `Finance`, `Buyer` | **فاقد قفل نقش** |
| **۲۸** | `/purchases/new` | GET | `purchases_ui.py` | `Admin`, `Buyer` | **فاقد قفل نقش** |
| **۲۹** | `/purchases/{order_id}` | GET | `purchases_ui.py` | `Admin`, `Finance`, `Buyer` | **فاقد قفل نقش** |
| **۳۰** | `/purchases/{order_id}/receive` | POST | `Admin`, `Buyer`, `Warehouse` | **فاقد قفل نقش** |
| **۳۱** | `/purchases/{order_id}/close-short` | POST | `purchases_ui.py` | `Admin`, `Buyer` | **فاقد قفل نقش** |
| **۳۲** | `/sales` | GET / POST | `sales_ui.py` | `Admin`, `Finance`, `Seller` | **فاقد قفل نقش** |
| **۳۳** | `/sales/new` | GET | `sales_ui.py` | `Admin`, `Seller` | **فاقد قفل نقش** |
| **۳۴** | `/sales/{order_id}` | GET | `sales_ui.py` | `Admin`, `Finance`, `Seller` | **فاقد قفل نقش** |
| **۳۵** | `/sales/{order_id}/deliver` | POST | `sales_ui.py` | `Admin`, `Seller`, `Warehouse` | **فاقد قفل نقش** |
| **۳۶** | `/sales/{order_id}/close-short` | POST | `sales_ui.py` | `Admin`, `Seller` | **فاقد قفل نقش** |
| **۳۷** | `/weighbridge` | GET / POST | `weighbridge_ui.py` | `Admin`, `Baskool` | **فاقد قفل نقش** |
| **۳۸** | `/weighbridge/new` | GET | `weighbridge_ui.py` | `Admin`, `Baskool` | **فاقد قفل نقش** |
| **۳۹** | `/weighbridge/{ticket_id}/second` | GET | `weighbridge_ui.py` | `Admin`, `Baskool` | **فاقد قفل نقش** |
| **۴۰** | `/weighbridge/{ticket_id}/complete` | POST | `weighbridge_ui.py` | `Admin`, `Baskool` | **فاقد قفل نقش** |
| **۴۱** | `/weighbridge/{ticket_id}/print` | GET | `weighbridge_ui.py` | لاگین‌شده | لاگین‌شده |
| **۴۲** | `/cutting` | GET / POST | `cutting_ui.py` | `Admin`, `Workshop` | **فاقد قفل نقش** |
| **۴۳** | `/cutting/new` | GET | `cutting_ui.py` | `Admin`, `Workshop` | **فاقد قفل نقش** |
| **۴۴** | `/bagging` | GET / POST | `bagging_ui.py` | `Admin`, `Workshop` | **فاقد قفل نقش** |
| **۴۵** | `/bagging/new` | GET | `bagging_ui.py` | `Admin`, `Workshop` | **فاقد قفل نقش** |
| **۴۶** | `/master-data/products` | GET | `master_data_ui.py` | لاگین‌شده | لاگین‌شده |
| **۴۷** | `/master-data/product` | POST | `master_data_ui.py` | `Admin` | `Depends(require_admin)` |
| **۴۸** | `/master-data/product/{id}/edit` | POST | `master_data_ui.py` | `Admin` | `Depends(require_admin)` |
| **۴۹** | `/master-data/product/{id}/toggle-status` | POST | `master_data_ui.py` | `Admin` | `Depends(require_admin)` |
| **۵۰** | `/master-data/category` | POST | `master_data_ui.py` | `Admin` | `Depends(require_admin)` |
| **۵۱** | `/master-data/warehouse` | POST | `master_data_ui.py` | `Admin` | `Depends(require_admin)` |
| **۵۲** | `/master-data/parties` | GET | `parties_ui.py` | لاگین‌شده | لاگین‌شده |
| **۵۳** | `/master-data/supplier` | POST | `parties_ui.py` | `Admin`, `Buyer` | **فقط `require_admin` (قفل برای خریدار!)** |
| **۵۴** | `/master-data/supplier/{id}/edit` | POST | `parties_ui.py` | `Admin`, `Buyer` | **فقط `require_admin` (قفل برای خریدار!)** |
| **۵۵** | `/master-data/customer` | POST | `parties_ui.py` | `Admin`, `Seller` | **فقط `require_admin` (قفل برای فروشنده!)** |
| **۵۶** | `/master-data/customer/{id}/edit` | POST | `parties_ui.py` | `Admin`, `Seller` | **فقط `require_admin` (قفل برای فروشنده!)** |
| **۵۷** | `/inventory/alerts` | GET | `alerts_ui.py` | لاگین‌شده | لاگین‌شده |
| **۵۸** | `/inventory/alerts/badge` | GET | `alerts_ui.py` | لاگین‌شده | لاگین‌شده |
| **۵۹** | `/compliance` | GET | `compliance_ui.py` | لاگین‌شده | لاگین‌شده |
| **۶۰** | `/compliance/export/ntsw` | GET | `compliance_ui.py` | لاگین‌شده | لاگین‌شده |
| **۶۱** | `/admin/audit-logs` | GET | `audit_ui.py` | فقط `Admin` | **فاقد قفل نقش (افشای لاگ به همه!)** |
| **۶۲** | `/admin/users` | GET / POST | `admin_ui.py` | فقط `Admin` | `Depends(require_admin)` |
| **۶۳** | `/admin/users/{user_id}/toggle` | POST | `admin_ui.py` | فقط `Admin` | `Depends(require_admin)` |

---

## ۵. کدهای فعلی توابع اصلی در فایل‌های کلیدی سیستم

### ۵.۱. فایل `src/api/inventory_ui.py` (توابع گردش کار تأیید و رد اسناد)

```python
# ==========================================
# ۱۰. گردش کار و تایید / رد اسناد (Package 0-C)
# ==========================================
@router.post("/transactions/{tx_id}/approve")
async def approve_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """تایید نهایی سند و اعمال در کاردکس موجودی و به‌روزرسانی پیشرفت سفارشات خرید/فروش"""
    require_roles(current_user, {"Admin", "Warehouse_Supervisor"})

    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    if tx.status == DocumentStatus.APPROVED:
        return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} قبلاً تأیید شده است"), status_code=303)

    # اگر سند خروجی است، کنترل موجودی
    if tx.transaction_type == TransactionType.OUT:
        cur_stock = InventoryService.get_current_stock(db, tx.product_id, tx.warehouse_id)
        if tx.quantity > cur_stock:
            raise HTTPException(status_code=400, detail=f"موجودی انبار ({cur_stock}) برای تایید سند خروج #{tx.id} به مقدار {tx.quantity} کافی نیست!")

    tx.status = DocumentStatus.APPROVED
    tx.approved_by_id = current_user.id
    tx.approved_at = datetime.now(timezone.utc)

    # ۱. به‌روزرسانی سفارش خرید مرتبط (received_quantity)
    if tx.purchase_order_id and tx.purchase_order_item_id:
        po_item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == tx.purchase_order_item_id).first()
        if po_item:
            po_item.received_quantity = (po_item.received_quantity or 0.0) + tx.quantity
            po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
            total_ordered = sum(it.quantity for it in po.items)
            total_rcvd = sum(it.received_quantity for it in po.items)
            if total_rcvd >= total_ordered:
                po.status = PurchaseOrderStatus.COMPLETED
            elif total_rcvd > 0:
                po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED
            else:
                po.status = PurchaseOrderStatus.CONFIRMED

    # ۲. به‌روزرسانی سفارش فروش مرتبط (delivered_quantity)
    if tx.sales_order_id and tx.sales_order_item_id:
        so_item = db.query(SalesOrderItem).filter(SalesOrderItem.id == tx.sales_order_item_id).first()
        if so_item:
            so_item.delivered_quantity = (so_item.delivered_quantity or 0.0) + tx.quantity
            so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
            total_ordered = sum(it.quantity for it in so.items)
            total_deliv = sum(it.delivered_quantity for it in so.items)
            if total_deliv >= total_ordered:
                so.status = SalesOrderStatus.COMPLETED
            elif total_deliv > 0:
                so.status = SalesOrderStatus.PARTIALLY_DELIVERED
            else:
                so.status = SalesOrderStatus.CONFIRMED

    db.commit()

    AuditService.log(
        db, action="APPROVE", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"تأیید نهایی سند انبار #{tx.id} توسط سرپرست انبار و اعمال قطعی در موجودی و سفارشات"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} با موفقیت تایید نهایی شد"), status_code=303)


@router.post("/transactions/{tx_id}/reject")
async def reject_transaction(
    tx_id: int,
    rejection_reason: str = Form("عدم تطابق فاکتور یا کسری بار"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """رد سند انبار با ثبت دلیل رسمی"""
    require_roles(current_user, {"Admin", "Warehouse_Supervisor"})

    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    tx.status = DocumentStatus.REJECTED
    tx.rejection_reason = rejection_reason
    db.commit()

    AuditService.log(
        db, action="REJECT", entity_name="StockTransaction", entity_id=str(tx.id),
        user_id=current_user.id, user_name=current_user.full_name or current_user.username,
        details=f"رد سند #{tx.id} به علت: {rejection_reason}"
    )
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} رد شد"), status_code=303)
```

---

### ۵.۲. فایل `src/api/purchases_ui.py` (تابع ارسال بار سفارش خرید به کارتابل انبار)

```python
@router.post("/{order_id}/receive", response_class=HTMLResponse)
async def receive_purchase_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    warehouse_id: int = Form(...),
    item_id: list[int] = Form(...),
    receive_qty: list[float] = Form(...)
):
    """
    ثبت درخواست رسید انبار برای سفارش خرید (Inbound Cartable Dispatch)
    ایجاد سند ورودی در وضعیت PENDING_APPROVAL جهت بررسی و تایید نهایی انباردار در کارتابل.
    """
    po = db.query(PurchaseOrder).filter(PurchaseOrder.id == order_id).first()
    if not po:
        raise HTTPException(status_code=404, detail="سفارش خرید یافت نشد")

    try:
        active_fy = InventoryService.get_active_fiscal_year(db)
        created_receipts = 0
        for it_id, r_qty in zip(item_id, receive_qty):
            if r_qty > 0:
                item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == it_id).first()
                if item:
                    # محاسبه اسناد در انتظار تایید کارتابل برای این ردیف سفارش (جهت کنترل سقف تلورانس)
                    pending_in_qty = (
                        db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0))
                        .filter(
                            StockTransaction.purchase_order_id == po.id,
                            StockTransaction.purchase_order_item_id == item.id,
                            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
                        )
                        .scalar()
                    )
                    # کنترل سقف ۵٪ تلورانس باسکول با لحاظ اسناد معلق کارتابل
                    max_allowed_receive = (item.quantity * 1.05) - item.received_quantity - pending_in_qty
                    if r_qty > (max_allowed_receive + 0.0001):
                        raise HTTPException(
                            status_code=400,
                            detail=f"مقدار دریافتی برای قلم {item.product.name} ({r_qty}) بیش از سقف مجاز سفارش به همراه ۵٪ تلورانس باسکول و اسناد معلق کارتابل (سقف باقی‌مانده: {max(0.0, round(max_allowed_receive, 3))}) است."
                        )

                    # صدور سند رسید موقت انبار در کارتابل (PENDING_APPROVAL)
                    tx = StockTransaction(
                        transaction_type=TransactionType.IN,
                        transaction_source=TransactionSource.PURCHASE.value,
                        product_id=item.product_id,
                        warehouse_id=warehouse_id,
                        quantity=r_qty,
                        unit_price=item.unit_price,
                        supplier_id=po.supplier_id,
                        purchase_order_id=po.id,
                        purchase_order_item_id=item.id,
                        reference_document=po.po_number,
                        status=DocumentStatus.PENDING_APPROVAL,
                        fiscal_year_id=active_fy.id if active_fy else None,
                        created_by_id=current_user.id
                    )
                    db.add(tx)
                    created_receipts += 1

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="PurchaseOrder",
            entity_id=str(po.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"صدور {created_receipts} قلم رسید موقت برای سفارش خرید {po.po_number} و ارسال به کارتابل انبار"
        )

        return RedirectResponse(
            url=f"/purchases/{po.id}?msg=" + quote(f"رسید موقت انبار صادر شد و جهت تایید نهایی و اعمال در موجودی به کارتابل انبار ارسال گردید."),
            status_code=303
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در صدور رسید انبار: {str(e)}")
```

---

### ۵.۳. فایل `src/api/sales_ui.py` (تابع ارسال حواله خروج به کارتابل انبار)

```python
@router.post("/{order_id}/deliver", response_class=HTMLResponse)
async def deliver_sales_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    warehouse_id: int = Form(...),
    item_id: list[int] = Form(...),
    deliver_qty: list[float] = Form(...)
):
    """
    ثبت درخواست حواله خروج انبار برای سفارش فروش (Outbound Cartable Dispatch)
    بررسی موجودی آزاد انبار و صدور سند OUT با وضعیت PENDING_APPROVAL جهت تایید نهایی انباردار.
    """
    so = db.query(SalesOrder).filter(SalesOrder.id == order_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="سفارش فروش یافت نشد")

    try:
        active_fy = InventoryService.get_active_fiscal_year(db)

        # بررسی سقف اعتبار مالی مشتری
        if so.customer and so.customer.credit_limit and so.customer.credit_limit > 0:
            if (so.total_amount or 0.0) > so.customer.credit_limit:
                raise HTTPException(
                    status_code=400,
                    detail=f"مبلغ کل سفارش ({so.total_amount:,.0f}) بیش از سقف اعتبار مالی مشتری ({so.customer.name}: {so.customer.credit_limit:,.0f}) است. تحویل کالا مجاز نمی‌باشد."
                )

        created_count = 0
        for it_id, d_qty in zip(item_id, deliver_qty):
            if d_qty > 0:
                item = db.query(SalesOrderItem).filter(SalesOrderItem.id == it_id).first()
                if item:
                    # ۱. بررسی سقف تحویل سفارش با احتساب اسناد معلق کارتابل خروج
                    pending_out_qty = (
                        db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0))
                        .filter(
                            StockTransaction.sales_order_id == so.id,
                            StockTransaction.sales_order_item_id == item.id,
                            StockTransaction.status == DocumentStatus.PENDING_APPROVAL
                        )
                        .scalar()
                    )
                    remaining_order_qty = (item.quantity * 1.05) - item.delivered_quantity - pending_out_qty
                    if d_qty > (remaining_order_qty + 0.0001):
                        raise HTTPException(
                            status_code=400,
                            detail=f"مقدار تحویلی قلم {item.product.name} ({d_qty}) بیشتر از مانده سفارش به همراه ۵٪ تلورانس و اسناد معلق کارتابل (سقف باقی‌مانده: {max(0.0, round(remaining_order_qty, 3))}) است."
                        )

                    # ۲. بررسی موجودی آزاد و قابل تخصیص انبار
                    avail_stock = InventoryService.get_available_stock(db, item.product_id, warehouse_id)
                    if d_qty > avail_stock:
                        raise HTTPException(
                            status_code=400,
                            detail=f"موجودی آزاد کالای {item.product.name} در این انبار ({avail_stock}) کافی نیست (درخواستی: {d_qty})."
                        )

                    # ۳. استخراج بهای تمام‌شده میانگین موزون برای کاردکس ریالی
                    avg_cost = InventoryService.get_weighted_average_cost(db, item.product_id, warehouse_id)

                    # ۴. صدور سند حواله خروج موقت (PENDING_APPROVAL) با سال مالی فعال
                    tx = StockTransaction(
                        transaction_type=TransactionType.OUT,
                        transaction_source=TransactionSource.SALES.value,
                        product_id=item.product_id,
                        warehouse_id=warehouse_id,
                        quantity=d_qty,
                        unit_price=avg_cost or item.unit_price,
                        customer_id=so.customer_id,
                        sales_order_id=so.id,
                        sales_order_item_id=item.id,
                        reference_document=so.so_number,
                        status=DocumentStatus.PENDING_APPROVAL,
                        fiscal_year_id=active_fy.id if active_fy else None,
                        created_by_id=current_user.id
                    )
                    db.add(tx)
                    created_count += 1

        db.commit()

        AuditService.log(
            db, action="CREATE", entity_name="SalesOrder",
            entity_id=str(so.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"صدور {created_count} قلم حواله خروج موقت برای سفارش فروش {so.so_number} و ارسال به کارتابل انبار"
        )

        return RedirectResponse(
            url=f"/sales/{so.id}?msg=" + quote("حواله خروج موقت صادر شد و جهت تایید نهایی انباردار به کارتابل انبار ارسال گردید."),
            status_code=303
        )
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در صدور حواله خروج انبار: {str(e)}")
```

---

### ۵.۴. فایل `src/api/weighbridge_ui.py` (تکمیل توزین دوم و یکپارچه‌سازی با کارتابل)

```python
@router.post("/{ticket_id}/complete", response_class=HTMLResponse)
async def complete_second_weighing(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    second_weight: float = Form(...),
    auto_create_transaction: bool = Form(True)
):
    """ثبت توزین دوم، محاسبه وزن خالص و یکپارچه‌سازی با کارتابل انبار (حذف ثبت دوبل)"""
    active_region = get_active_region(request)
    is_tr = (active_region.code == Region.TR)

    ticket = db.query(WeighbridgeTicket).filter(WeighbridgeTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="قبض باسکول یافت نشد")

    if ticket.stock_transaction_id:
        error_msg = "Bu kantar fişi için zaten bir depo belgesi oluşturulmuş!" if is_tr else "برای این قبض باسکول قبلاً سند انبار صادر شده است (جلوگیری از ثبت دوبل)."
        raise HTTPException(status_code=400, detail=error_msg)

    try:
        if ticket.gross_weight and ticket.gross_weight > 0:
            # توزین اول ناخالص بوده (بار ورودی/خرید)، توزین دوم تار (خالی) است
            ticket.tare_weight = second_weight
        else:
            # توزین اول تار بوده (بار خروجی/فروش)، توزین دوم ناخالص (پر) است
            ticket.gross_weight = second_weight

        if ticket.gross_weight <= ticket.tare_weight:
            err = "Brüt ağırlık dara ağırlığından büyük olmalıdır!" if is_tr else f"وزن پر (ناخالص: {ticket.gross_weight} کیلوگرم) نمی‌تواند کمتر یا مساوی وزن خالی (تار: {ticket.tare_weight} کیلوگرم) باشد."
            raise HTTPException(status_code=400, detail=err)

        ticket.net_weight = round(ticket.gross_weight - ticket.tare_weight, 3)
        ticket.status = WeighbridgeStatus.COMPLETED
        ticket.completed_at = datetime.now(timezone.utc)

        # بررسی نهایی سقف تناژ پلیس‌راه یا KGM
        if is_tr:
            is_kgm_over, kgm_limit, _ = check_kgm_weight_limit(ticket.gross_weight, ticket.truck_type)
            ticket.max_allowed_weight = kgm_limit
            ticket.is_overweight = is_kgm_over
        else:
            if ticket.gross_weight > ticket.max_allowed_weight:
                ticket.is_overweight = True

        # محاسبه وزن متناسب با واحد کالا (تن یا کیلوگرم)
        is_ton = ticket.product and ticket.product.uom in ("تن", "Ton", "ton")
        net_qty = (ticket.net_weight / 1000.0) if is_ton else ticket.net_weight

        # بازیابی سال مالی فعال
        active_fy = InventoryService.get_active_fiscal_year(db)

        # استخراج ردیف سفارش و تعیین قیمت متناظر (جلوگیری از باگ قیمت صفر در کاردکس)
        po_item = None
        so_item = None
        unit_price = 0.0

        if ticket.purchase_order_id:
            po_item = db.query(PurchaseOrderItem).filter(
                PurchaseOrderItem.purchase_order_id == ticket.purchase_order_id,
                PurchaseOrderItem.product_id == ticket.product_id
            ).first()
            if po_item:
                unit_price = po_item.unit_price or 0.0
        elif ticket.sales_order_id:
            so_item = db.query(SalesOrderItem).filter(
                SalesOrderItem.sales_order_id == ticket.sales_order_id,
                SalesOrderItem.product_id == ticket.product_id
            ).first()
            unit_price = InventoryService.get_weighted_average_cost(db, ticket.product_id, ticket.warehouse_id)

        # بررسی وجود سند در انتظار تأیید در کارتابل انبار برای سفارش مرتبط (فقط اسنادی که هنوز به هیچ قبض باسکولی وصل نیستند)
        pending_tx = None
        if ticket.purchase_order_id:
            pending_tx = db.query(StockTransaction).filter(
                StockTransaction.purchase_order_id == ticket.purchase_order_id,
                StockTransaction.product_id == ticket.product_id,
                StockTransaction.status == DocumentStatus.PENDING_APPROVAL,
                StockTransaction.weighbridge_ticket_id.is_(None)
            ).first()
        elif ticket.sales_order_id:
            pending_tx = db.query(StockTransaction).filter(
                StockTransaction.sales_order_id == ticket.sales_order_id,
                StockTransaction.product_id == ticket.product_id,
                StockTransaction.status == DocumentStatus.PENDING_APPROVAL,
                StockTransaction.weighbridge_ticket_id.is_(None)
            ).first()

        if pending_tx:
            # به‌روزرسانی همان سند کارتابل با وزن باسکول و تخصصی‌سازی مشخصات
            pending_tx.quantity = round(net_qty, 3)
            pending_tx.weighbridge_ticket_id = ticket.id
            pending_tx.reference_document = f"{pending_tx.reference_document or ''} | قبض باسکول {ticket.ticket_number}".strip(" |")
            if po_item:
                pending_tx.purchase_order_item_id = po_item.id
                if not pending_tx.unit_price or pending_tx.unit_price == 0:
                    pending_tx.unit_price = unit_price
            elif so_item:
                pending_tx.sales_order_item_id = so_item.id
                if not pending_tx.unit_price or pending_tx.unit_price == 0:
                    pending_tx.unit_price = unit_price
            if not pending_tx.fiscal_year_id and active_fy:
                pending_tx.fiscal_year_id = active_fy.id
            ticket.stock_transaction_id = pending_tx.id
        else:
            # ایجاد یک سند در انتظار تأیید (PENDING_APPROVAL) در کارتابل انبار با قیمت مشخص
            tx_type = TransactionType.IN if (ticket.supplier_id or ticket.purchase_order_id) else TransactionType.OUT
            tx_src = TransactionSource.PURCHASE.value if tx_type == TransactionType.IN else TransactionSource.SALES.value
            tx = StockTransaction(
                transaction_type=tx_type,
                transaction_source=tx_src,
                product_id=ticket.product_id,
                warehouse_id=ticket.warehouse_id,
                quantity=round(net_qty, 3),
                unit_price=unit_price,
                supplier_id=ticket.supplier_id,
                customer_id=ticket.customer_id,
                purchase_order_id=ticket.purchase_order_id,
                purchase_order_item_id=po_item.id if po_item else None,
                sales_order_id=ticket.sales_order_id,
                sales_order_item_id=so_item.id if so_item else None,
                weighbridge_ticket_id=ticket.id,
                reference_document=f"قبض باسکول {ticket.ticket_number}",
                status=DocumentStatus.PENDING_APPROVAL,
                fiscal_year_id=active_fy.id if active_fy else None,
                created_by_id=current_user.id
            )
            db.add(tx)
            db.flush()
            ticket.stock_transaction_id = tx.id

        db.commit()

        AuditService.log(
            db, action="APPROVE", entity_name="WeighbridgeTicket",
            entity_id=str(ticket.id), user_id=current_user.id, user_name=current_user.full_name or current_user.username,
            details=f"تکمیل توزین دوم قبض {ticket.ticket_number} - وزن خالص: {ticket.net_weight} کیلوگرم"
        )

        return RedirectResponse(
            url=f"/weighbridge/{ticket.id}/print",
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"خطا در قطعی کردن توزین: {str(e)}")
```

---

## ۶. طرح اصلاحی و نقشه راه پیشنهادی برای معمار سیستم (Architectural Remediation Plan)

برای برطرف‌سازی کامل تداخل‌های کشف‌شده و آماده‌سازی سیستم برای نسخه نهایی تجاری، اقدامات زیر ضروری است:

### گام ۱: استانداردسازی و تعمیم گارد RBAC در بک‌اند (`Backend RBAC Harmonization`)
1. انتقال تابع `require_roles` از `inventory_ui.py` به `src/core/dependencies.py` به صورت یک Dependency کارخانه‌ای (Factory Dependency):
   ```python
   def allow_roles(*roles: str):
       def role_checker(current_user: User = Depends(get_current_user)) -> User:
           user_roles = {r.name for r in current_user.roles}
           if "Admin" in user_roles:
               return current_user
           if not user_roles.intersection(set(roles)):
               raise HTTPException(status_code=403, detail="عدم دسترسی به این عملیات")
           return current_user
       return role_checker
   ```
2. اعمال گاردها روی روترها:
   - `purchases_ui.py`: اضافه کردن گارد `allow_roles("Admin", "Finance_Manager", "Procurement_Officer")`
   - `sales_ui.py`: اضافه کردن گارد `allow_roles("Admin", "Finance_Manager", "Sales_Officer")`
   - `weighbridge_ui.py`: اضافه کردن گارد `allow_roles("Admin", "Weighbridge_Operator")`
   - `cutting_ui.py` و `bagging_ui.py`: اضافه کردن گارد `allow_roles("Admin", "Production_Operator")`
   - `audit_ui.py`: اضافه کردن گارد `Depends(require_admin)` جهت جلوگیری از نشت اطلاعات امنیتی.
   - `parties_ui.py`: مجاز کردن `Procurement_Officer` برای ثبت تأمین‌کننده، و `Sales_Officer` برای ثبت مشتری.

### گام ۲: تفکیک دسترسی‌ها و اصلاح کارتابل در داشبورد (`Dashboard Cleansing`)
1. محصور کردن بلوک کارتابل `pending_txs` در `dashboard.html` داخل شرط:
   `{% if (is_admin or is_warehouse) and pending_txs and pending_txs | length > 0 %}`
2. افزودن مودال ثبت دلیل رد سند در داشبورد مشابه `transactions.html`.
3. اصلاح کارت‌های آماری:
   - شمارش فقط اسناد `status == DocumentStatus.APPROVED` برای `tx_count`.
   - استخراج تعداد اقلامی که موجودی آنها در انبارها بیشتر از صفر است برای `stock_balances`.
   - فارسی‌سازی نام نقش با دیکشنری نقش‌های سازمانی (`مدیر ارشد`, `مدیر مالی`, `سرپرست انبار`, ...).

### گام ۳: حل باگ صفحه‌بندی کارتابل در `transactions.html`
- در تابع `list_transactions` در `inventory_ui.py`، متغیر `pending_txs` به صورت مستقل از کوئری صفحه‌بندی، با فیلتر `StockTransaction.status == DocumentStatus.PENDING_APPROVAL` واکشی و به Template context فرستاده شود تا وابستگی تمپلیت به لیست ۱۰تایی صفحه جاری حذف گردد.

### گام ۴: ایمن‌سازی زنجیره توزین و کارتابل (Weighbridge & Cartable Lock)
- اضافه کردن کلید یکتای اتصال یا یک فلگ رزرو به گونه‌ای که با ثبت توزین اول، سند مرتبط به حالت قفل برود و دکمه «تخلیه بار» در سفارش خرید، در صورت وجود قبض باسکول باز، هشدار داده و از ایجاد دوباره سند جلوگیری کند.
- فرمول تبدیل وزن باسکول به واحد فرعی/اصلی کالا با بررسی `nominal_weight` تکمیل گردد.
