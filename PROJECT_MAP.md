# 🗺️ نقشه جامع و اطلس معماری سامانه نکسوس‌پـور (NexusPour ERP)

> **سند مرجع سریع و راهنمای کامل برای هوش مصنوعی (AI Agents) و توسعه‌دهندگان**  
> این سند برای حفظ دائمی کانتکست، جلوگیری از مصرف بیهوده توکن و دسترسی فوری به تمام جزئیات فنی و ساختاری پروژه تدوین شده است. هر ایجنتی با مطالعه این تک‌فایل، ۱۰۰٪ به وضعیت پروژه مسلط می‌شود.

---

## 📌 ۱. اطلاعات پایه و حقوق مالکیت معنوی (Brand Identity)
* **نام رسمی تجاری:** نکسوس‌پـور | NexusPour ERP
* **نسخه فعال:** Version 2.0.0 (Enterprise Logistics & Storage Edition)
* **مالکیت، طراحی و مهندسی نرم‌افزار:** **امید پورمحمود (Omid Pourmahmoud)**
* **ریپازیتوری گیت‌هاب:** `https://github.com/patronsafety-create/storage_management.git`
* **شاخه اصلی پایدار (Production Branch):** `stable-erp-core`

---

## 🔑 ۲. اطلاعات احراز هویت و دسترسی‌های پیش‌فرض
* **کاربر مدیر کل (Super Admin):**
  * نام کاربری: `admin` | رمز عبور: `1234`
  * دسترسی‌ها: دسترسی نامحدود به تمامی بخش‌ها + منوی مدیریت کاربران، ثبت انبار جدید، ثبت کالای جدید.
* **کاربر اپراتور انبار (Warehouse Operator):**
  * نام کاربری: `operator` | رمز عبور: `operator123`
  * دسترسی‌ها: ثبت اسناد ورود/خروج، انتقال، انبارگردانی، مشاهده کاردکس و موجودی (بدون دسترسی به مدیریت کاربران و تعاریف پایه).
* **کلید امنیتی توکن (SECRET_KEY):** در `.env` ذخیره شده است.
* **الگوریتم رمزنگاری کلمات عبور:** `Argon2id` (بدون تکیه بر passlib به دلیل باگ‌های نسخه جدید).

---

## 🏗️ ۳. استک فنی و معماری نرم‌افزار (Tech Stack)
* **بک‌اند:** Python 3.11 + FastAPI (روترهای تفکیک‌شده در `src/api/`).
* **پایگاه‌داده عملیاتی (Production):** PostgreSQL 15 در کانتینر ایزوله داکر با ولوم پایدار `pgdata`.
* **ORM و مایگریشن:** SQLAlchemy 2.x + Alembic (متصل به Base واحد).
* **فرانت‌اند و UI:** قالب‌های Jinja2 + Bootstrap 5.3 (RTL) + استایل اختصاصی Dark Glassmorphism.
* **تایپوگرافی و بومی‌سازی:** فونت وزیرمتن (Vazirmatn) با فعال‌سازی ویژگی OpenType `font-feature-settings: "ss01" 1` + اسکریپت کلاینت جهت تبدیل ۱۰۰٪ کلیه ارقام و اعداد به فارسی (`۰-۹`).
* **نمودارها:** Chart.js با نمودار کیکی (Doughnut) تحلیلی و جعبه ابزار فارسی.

---

## 🌐 ۴. زیرساخت سرور و استقرار ابری (Oracle Cloud VPS)
* **سرور:** Oracle Cloud Infrastructure (Ubuntu 22.04 LTS - معماری ARM64 Neoverse-N1).
* **مشخصات سرور:** ۴ هسته CPU و ۲۴ گیگابایت رم (بیش از ۲۰ گیگابایت رم و ۳۷ گیگابایت دیسک کاملاً آزاد است).
* **آدرس IP سرور:** `79.76.100.127`
* **مسیر پروژه روی سرور:** `/home/ubuntu/storage_management`
* **سیاست ایزولاسیون:** ۹ ربات تلگرامی کاربر روی سرور فعالند که کاملاً دست‌نخورده باقی مانده‌اند و انبارداری در کانتینرهای مجزای داکر با `restart: always` اجرا می‌شود.
* **پورت‌های کانتینر وب:** پورت `80` و `8000` (اتصال مستقیم به اپلیکیشن).
* **تونل ابری امن:** سرویس سیستم‌دی `storage-tunnel.service` با ابزار Cloudflare Tunnel روی سرور فعال است.

---

## 🗄️ ۵. ساختار جداول پایگاه‌داده (Database Schema)

```mermaid
erDiagram
    users ||--o{ user_roles : has
    roles ||--o{ user_roles : has
    users ||--o{ stock_transactions : creates
    warehouses ||--o{ stock_transactions : records
    products ||--o{ stock_transactions : tracks
    product_categories ||--o{ products : categorizes
    product_categories ||--o{ product_categories : parent_of
    suppliers ||--o{ stock_transactions : supplies
    customers ||--o{ stock_transactions : purchases
    suppliers ||--o{ purchase_orders : receives
    purchase_orders ||--o{ purchase_order_items : contains
    warehouses ||--o{ weighbridge_tickets : weighs
    products ||--o{ weighbridge_tickets : weighs

    suppliers {
        int id PK
        string code
        string name
        string contact_person
        string phone
        string national_id
        boolean is_active
    }
    customers {
        int id PK
        string code
        string name
        string contact_person
        string phone
        string national_id
        float credit_limit
        boolean is_active
    }
    purchase_orders {
        int id PK
        string po_number
        int supplier_id FK
        string status
        float total_amount
    }
    weighbridge_tickets {
        int id PK
        string ticket_number
        string truck_plate
        string driver_name
        float gross_weight
        float tare_weight
        float net_weight
        string status
    }
    cutting_orders {
        int id PK
        string order_number
        int product_id FK
        float original_length
        float cut_length
        float remnant_length
        string status
    }
    bagging_orders {
        int id PK
        string order_number
        int bulk_product_id FK
        int packaged_product_id FK
        float bulk_tonnage_used
        float packages_produced
        string status
    }
    audit_logs {
        int id PK
        int user_id FK
        string action
        string entity_name
        string ip_address
        datetime created_at
    }
    users {
        int id PK
        string username
        string hashed_password
        string full_name
        boolean is_active
    }
    roles {
        int id PK
        string name
        string description
    }
    warehouses {
        int id PK
        string name
        string location
    }
    product_categories {
        int id PK
        string name
        string code
        int parent_id FK
        string description
    }
    products {
        int id PK
        string sku
        string name
        string uom
        string secondary_uom
        float nominal_weight
        string irc_code
        string hs_code
        int category_id FK
        string brand
        string size
        float length
        float thickness
        string grade
        string standard
        float min_stock
        float max_stock
        float reorder_point
        string description
        boolean is_active
    }
    stock_transactions {
        int id PK
        string transaction_type
        int product_id FK
        int warehouse_id FK
        int supplier_id FK
        int customer_id FK
        float quantity
        float secondary_quantity
        string secondary_uom
        float unit_price
        float freight_cost
        float insurance_cost
        float weighbridge_cost
        float bol_tonnage
        float shrinkage_tolerance_pct
        float final_landed_cost
        string heat_number
        string mtc_number
        string waybill_number
        string tracking_code
        string status
        string batch_number
        string reference_document
        datetime created_at
        int created_by_id FK
    }
```

* **نکته کلیدی مدل‌ها:**
  * جدول `product_categories` ساختار سلسله‌مراتبی و درختی گروه‌های کالایی را پشتیبانی می‌کند.
  * در مدل `Product`، فیلدهای صنعتی و متالورژی (برند، سایز، طول، ضخامت، گرید، استاندارد، IRC، HS Code)، واحد فرعی (`secondary_uom`)، وزن اسمی (`nominal_weight`) و پارامترهای کنترل انبارداری (`min_stock`, `reorder_point`, `max_stock`) اضافه شده‌اند.
  * در مدل `StockTransaction` ستون‌های دو واحدی، بهای تمام‌شده تجمیعی (`freight_cost`, `insurance_cost`, `weighbridge_cost`, `final_landed_cost`)، افت بارنامه، مشخصات متالورژی (`heat_number`, `mtc_number`)، انطباق سامانه تجارت (`waybill_number`, `tracking_code`) و چرخه تأیید (`status`) پیاده‌سازی شده‌اند.
  * مدل‌های تخصصی `Supplier`، `Customer`، `PurchaseOrder`، `WeighbridgeTicket`، `CuttingOrder`، `BaggingOrder` و `AuditLog` به صورت کامل یکپارچه و به دیتابیس متصل شده‌اند.

---

## 🗺️ ۶. نقشه کامل مسیرها و روت‌های سامانه (Endpoints & Pages)

| ردیف | مسیر (Route) | متد | کارکرد و قابلیت | دسترسی |
| :---: | :--- | :---: | :--- | :---: |
| **۱** | `/login` | GET/POST | صفحه ورود و احراز هویت با ظاهر نئونی دارک نکسوس‌پور | عمومی |
| **۲** | `/logout` | GET | خروج از حساب کاربری و باطل‌سازی کوکی سشن | همه کاربران |
| **۳** | `/dashboard` | GET | داشبورد مدیریتی، کارت‌های آمار و نمودار کیکی سهم انبارها | لاگین‌شده |
| **۴** | `/inventory/transaction` | GET/POST | ثبت رسید/حواله دو واحدی با بهای تمام‌شده، هزینه‌های سربار، افت بارنامه و متالورژی | لاگین‌شده |
| **۵** | `/inventory/transactions` | GET | جدول تاریخچه اسناد با امکان تایید/رد سند (Approval Workflow) و مودال دلایل رد | لاگین‌شده |
| **۶** | `/inventory/transactions/{id}/approve` | POST | تایید نهایی سند و اعمال در کاردکس موجودی | مدیر/انباردار |
| **۷** | `/inventory/transactions/{id}/reject` | POST | رد سند با ثبت علت و عدم اعمال در موجودی | مدیر/انباردار |
| **۸** | `/inventory/transactions/{id}/mtc` | GET | **شناسنامه رسمی متالورژی کالا (MTC Certificate):** آنالیز شیمیایی و مکانیکی جهت چاپ | لاگین‌شده |
| **۹** | `/inventory/products/{id}/label` | GET | **چاپ لیبل بارکد و QR Code استاندارد ۱۰۰x۷۰ میلی‌متر** با خطوط برش | لاگین‌شده |
| **۱۰** | `/inventory/transfer` | GET/POST | **انتقال بین انبارها:** کسر از انبار مبدأ و افزودن به مقصد با مرجع واحد | لاگین‌شده |
| **۱۱** | `/inventory/stocktaking` | GET/POST | **انبارگردانی:** مقایسه شمارش عینی با سیستم و صدور سند خودکار تعدیل | لاگین‌شده |
| **۱۲** | `/inventory/returns/new` | GET/POST | **اسناد برگشت از خرید و برگشت از فروش:** اتصال به سند مرجع و برگشت موجودی | لاگین‌شده |
| **۱۳** | `/inventory/balance` | GET | گزارش تفصیلی موجودی لحظه‌ای (مقداری، دو واحدی و ریالی) | لاگین‌شده |
| **۱۴** | `/inventory/alerts` | GET | **مرکز هشدارهای هوشمند انبار:** کالاهای زیر نقطه سفارش و کالاهای راکد (+۹۰ روز) | لاگین‌شده |
| **۱۵** | `/inventory/alerts/badge` | GET | وب‌سرویس تعداد هشدارهای فعال جهت نمایش زنده روی آیکون زنگوله نوبار | لاگین‌شده |
| **۱۶** | `/purchases` | GET | **مدیریت سفارشات خرید (PO):** لیست، فیلترها و شاخص‌های مالی سفارشات | لاگین‌شده |
| **۱۷** | `/purchases/new` | GET/POST | فرم ثبت سفارش خرید جدید با اقلام چندگانه | لاگین‌شده |
| **۱۸** | `/purchases/{id}` | GET | مشاهده جزئیات سفارش خرید و دکمه تبدیل با ۱ کلیک به رسید انبار | لاگین‌شده |
| **۱۹** | `/purchases/{id}/receive` | POST | **تبدیل هوشمند سفارش خرید به رسید انبار:** ثبت رسید و بستن خودکار PO | لاگین‌شده |
| **۲۰** | `/weighbridge` | GET | **زیرسیستم باسکول تریلی:** لیست نوبت‌ها، وضعیت توزین، ترافیک و مغایرت وزن | لاگین‌شده |
| **۲۱** | `/weighbridge/new` | GET/POST | ثبت توزین اول تریلی (پر یا خالی) و بررسی سقف تناژ پلیس‌راه | لاگین‌شده |
| **۲۲** | `/weighbridge/{id}/second` | GET | فرم ثبت توزین مرحله دوم | لاگین‌شده |
| **۲۳** | `/weighbridge/{id}/complete` | POST | ثبت توزین دوم، محاسبه خالص و صدور مستقیم سند انبار | لاگین‌شده |
| **۲۴** | `/weighbridge/{id}/print` | GET | **برگه رسمی قبض باسکول دیجیتال:** فرمت استاندارد پرینت با بارکد و پلاک | لاگین‌شده |
| **۲۵** | `/cutting` | GET | **مدیریت دستورات برش و انبار ته‌شاخه آهن:** محاسبه بهای تمام‌شده ته‌شاخه | لاگین‌شده |
| **۲۶** | `/cutting/new` | GET/POST | ثبت دستور برش جدید و انتقال خودکار ته‌شاخه به انبار ضایعات/ته‌شاخه | لاگین‌شده |
| **۲۷** | `/bagging` | GET | **زیرسیستم کیسه‌گیری فله به جامبوبگ اوره:** مانیتورینگ ضریب مصرف و ریزش | لاگین‌شده |
| **۲۸** | `/bagging/new` | GET/POST | ثبت عملیات کیسه‌گیری فله و محاسبه هزینه دستمزد و بسته‌بندی | لاگین‌شده |
| **۲۹** | `/compliance` | GET | **داشبورد انطباق با سامانه‌های دولتی:** مانیتورینگ کدهای IRC، بارنامه برخط و سامانه تجارت | لاگین‌شده |
| **۳۰** | `/compliance/export/ntsw` | GET | **دانلود خروجی اکسل ویژه سامانه جامع تجارت (ntsw.ir):** با کدگذاری UTF-8 BOM | لاگین‌شده |
| **۳۱** | `/admin/audit-logs` | GET | **لاگ جامع حسابرسی و ردپای امنیتی:** گزارش رویدادها، تغییرات اسناد و IP کاربران | ادمین |
| **۳۲** | `/master-data/products` | GET | **کاتالوگ جامع کالاها:** مشخصات متالورژی، موجودی لحظه‌ای، فیلتر و چاپ لیبل | لاگین‌شده |
| **۳۳** | `/master-data/product` | POST | ثبت کالای جدید با کدینگ SKU و ویژگی‌های فنی | ادمین |
| **۳۴** | `/master-data/product/{id}/edit` | POST | ویرایش مشخصات و پارامترهای کنترل موجودی کالا | ادمین |
| **۳۵** | `/master-data/parties` | GET/POST | **مدیریت طرف‌های تجاری:** ثبت و ویرایش تأمین‌کنندگان و مشتریان با شناسه ملی | لاگین‌شده |
| **۳۶** | `/admin/users` | GET/POST | پنل مدیریت کاربران، ایجاد کاربر جدید و تخصیص نقش | ادمین |
| **۳۷** | `/api/stock-check` | GET | وب‌سرویس AJAX برای بررسی موجودی آنی کالا در انبار انتخابی | لاگین‌شده |

---

## 💡 ۷. تجربیات حل باگ و نکات کلیدی برای ایجنت‌های بعدی (Gotchas)
1. **لودینگ مودال‌های بوت‌استرپ:** مودال‌ها نباید داخل تگ‌های دارای `transform` یا انیمیشن CSS قرار گیرند؛ در `base.html` یک بلاک اختصاصی به نام `{% block modals %}` خارج از کانتینر اصلی قرار داده شده است.
2. **ارتباطات SQLAlchemy:** در کلاس `StockTransaction` از تعریف متغیر مترادف بدون `synonym` خودداری شود؛ رابطه `created_by = relationship("User", foreign_keys=[created_by_id])` تعریف شده است.
3. **پوشه static:** در فایل `src/api/main.py` قبل از مانت کردن پوشه استاتیک، `os.makedirs("static", exist_ok=True)` قرار گرفته تا در سرورهای کلود بدون پوشه خالی به خطا نخورد.
4. **اعداد فارسی:** فونت وزیرمتن با ویژگی `font-feature-settings: "ss01" 1` فعال است و اسکریپت `toPersianDigits` در DOM متون را به فارسی برمی‌گرداند.

---

## ⚡ ۸. دستورات سریع راه‌اندازی (Quick Commands)
```powershell
# اجرای لوکال در ویندوز با داکر
docker compose up -d

# مشاهده لاگ کانتینر برنامه
docker compose logs app -f

# بررسی وضعیت سرور اوراکل از طریق SSH
ssh oracle "cd /home/ubuntu/storage_management && docker compose ps"
```
