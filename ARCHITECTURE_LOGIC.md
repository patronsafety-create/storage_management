# 🏛️ معماری منطق تجاری، جریان مالی و زنجیره انبارداری (NexusPour ERP)
> **سند تحلیلی ویژه بررسی با مهندس ارشد سیستم‌های مالی و حسابداری (Financial Systems Review)**  
> **مالکیت، طراحی و معماری نرم‌افزار:** امید پورمحمود (Omid Pourmahmoud)  
> **نسخه استقرار:** 2.5.0 Enterprise Edition (Updated Post-Phase Implementation)  
> **هدف سند:** تشریح ساختار دیتابیس، استیت ماشین گردش اسناد خرید و فروش، نحوه محاسبه و اثرگذاری بر کاردکس انبار، سازوکار اسناد اصلاحیه، عملیات پایان سال مالی و نقاط کنترل ثبت تکراری.

---

## ۱. ساختار کامل دیتابیس (Database Schema)

پایگاه‌داده عملیاتی بر بستر **PostgreSQL 15** با لایه ORM در **SQLAlchemy 2.x** طراحی شده است. ساختار کلیه جداول، فیلدها، نوع داده‌ها و کلیدهای خارجی به شرح زیر است:

### ۱.۱. جدول `users` (کاربران سامانه)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه کاربر |
| `username` | String | Unique, Index, Not Null | نام کاربری |
| `hashed_password` | String | Not Null | رمز عبور هش‌شده (Argon2id) |
| `full_name` | String | Nullable | نام و نام خانوادگی |
| `is_active` | Boolean | Default True, Not Null | وضعیت فعال بودن |
| `created_at` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت |

### ۱.۲. جدول `roles` (نقش‌های دسترسی RBAC)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه نقش |
| `name` | String | Unique, Index, Not Null | نام نقش (Admin, Operator) |
| `description` | String | Nullable | شرح دسترسی‌ها |

### ۱.۳. جدول واسط `user_roles` (تخصیص نقش‌ها - N:M)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `user_id` | Integer | PK, FK `users.id` (CASCADE) | شناسه کاربر |
| `role_id` | Integer | PK, FK `roles.id` (CASCADE) | شناسه نقش |

### ۱.۴. جدول `product_categories` (دسته‌بندی درختی کالاها)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه گروه کالا |
| `name` | String | Unique, Not Null | نام دسته‌بندی |
| `code` | String | Unique, Nullable | کد گروه کالا (مانند `STL-RAW`) |
| `description` | String | Nullable | توضیحات گروه |
| `parent_id` | Integer | FK `product_categories.id`, Nullable | شناسه گروه والد |

### ۱.۵. جدول `products` (کاتالوگ کالاها و مشخصات متالورژی/مالیاتی)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه یکتای کالا |
| `name` | String | Unique, Not Null | نام تجاری کالا |
| `uom` | String | Not Null, Default "عدد" | واحد سنجش اصلی (تن، کیلوگرم، شاخه، عدد) |
| `secondary_uom` | String | Nullable | واحد سنجش فرعی (شاخه، بندیل، کیسه) |
| `nominal_weight` | Float | Nullable, Default 0.0 | وزن اشتال هر شاخه/بسته (کیلوگرم) |
| `sku` | String | Unique, Index, Nullable | کدینگ یا بارکد کالا |
| `irc_code` | String | Nullable | شناسه کالا در سامانه جامع تجارت ایران |
| `hs_code` | String | Nullable | کد تعرفه گمرکی بین‌المللی (HS Code) |
| `gtip_code` | String | Nullable | کد ۱۲ رقمی تعرفه ترکیه (GTİP) |
| `tse_standard` | String | Nullable | استاندارد ملی متالورژی ترکیه (TS 708) |
| `category_id` | Integer | FK `product_categories.id`, Nullable | گروه کالا |
| `brand` | String | Nullable | کارخانه سازنده (ذوب‌آهن، مبارکه، خوزستان و ...) |
| `size` | String | Nullable | سایز ابعادی (مثلاً ۱۶، IPE 20) |
| `length` | Float | Nullable | طول شاخه به متر (۶ یا ۱۲) |
| `thickness` | Float | Nullable | ضخامت به میلی‌متر |
| `grade` | String | Nullable | گرید آلیاژی (A3, 3SP, 5SP, Gr46) |
| `standard` | String | Nullable | استاندارد تولید (DIN 488, ASTM) |
| `min_stock` | Float | Nullable, Default 0.0 | حداقل موجودی امن |
| `max_stock` | Float | Nullable, Default 0.0 | سقف ظرفیت انبارداری |
| `reorder_point` | Float | Nullable, Default 0.0 | نقطه سفارش مجدد |
| `description` | String | Nullable | توضیحات |
| `is_active` | Boolean | Default True | وضعیت عرضه |
| `created_at` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت |

### ۱.۶. جدول `warehouses` (انبارها)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه انبار |
| `name` | String | Unique, Not Null | نام انبار یا محوطه دپو |

### ۱.۷. جدول `suppliers` (تأمین‌کنندگان)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه تأمین‌کننده |
| `name` | String | Unique, Not Null | نام شرکت یا شخص |
| `code` | String | Unique, Nullable | کد تأمین‌کننده (مثلاً `SUP-001`) |
| `contact_person` | String | Nullable | شخص رابط بازرگانی |
| `phone` | String | Nullable | شماره تماس |
| `email` | String | Nullable | پست الکترونیکی |
| `address` | String | Nullable | آدرس کارخانه یا دفتر |
| `national_id` | String | Nullable | شناسه ملی اشخاص حقوقی / کد ملی |
| `vkn` | String | Nullable | شناسه مالیاتی ترکیه (VKN) |
| `tax_office` | String | Nullable | اداره مالیاتی ترکیه (Vergi Dairesi) |
| `mersis_no` | String | Nullable | شماره ثبت بازرگانی ترکیه |
| `country_code` | String | Default "IR" | کد کشور (IR یا TR) |
| `is_active` | Boolean | Default True | وضعیت اعتبار تجاری |
| `created_at` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت |

### ۱.۸. جدول `customers` (مشتریان و خریداران)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه مشتری |
| `name` | String | Unique, Not Null | نام خریدار / شرکت پروژه |
| `code` | String | Unique, Nullable | کد مشتری (مثلاً `CUST-001`) |
| `contact_person` | String | Nullable | رابط بازرگانی |
| `phone` | String | Nullable | تلفن همراه |
| `email` | String | Nullable | ایمیل |
| `address` | String | Nullable | نشانی تحویل و تخلیه |
| `national_id` | String | Nullable | کد ملی / شناسه اقتصادی |
| `vkn` | String | Nullable | شناسه مالیاتی ترکیه (VKN) |
| `tax_office` | String | Nullable | حوزه مالیاتی ترکیه |
| `mersis_no` | String | Nullable | شماره مرسیس ترکیه |
| `country_code` | String | Default "IR" | کد کشور |
| `credit_limit` | Float | Default 0.0 | سقف اعتبار اسنادی / ریالی |
| `is_active` | Boolean | Default True | وضعیت حساب مشتری |
| `created_at` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت |

### ۱.۹. جدول `fiscal_years` (سال‌ها و دوره‌های مالی)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه سال مالی |
| `name` | String | Unique, Not Null | عنوان سال مالی (مثلاً «سال مالی ۱۴۰۳») |
| `start_date` | String | Not Null | تاریخ شروع دوره (شمسی/میلادی) |
| `end_date` | String | Not Null | تاریخ پایان دوره (شمسی/میلادی) |
| `is_active` | Boolean | Default True | نشانگر سال مالی جاری و فعال |
| `is_closed` | Boolean | Default False | نشانگر قفل و بسته‌شدن دوره مالی |
| `closed_at` | DateTime(tz=True) | Nullable | زمان رسمی بستن دوره |
| `closed_by_id` | Integer | FK `users.id`, Nullable | مدیر بسته‌کننده سال مالی |

### ۱.۱۰. جدول `stock_transactions` (اسناد انبار، رسید، حواله، کاردکس و اصلاحیه)
*محدودیت جدول:* `CHECK (quantity >= 0)` (پشتیبانی از اصلاحات ریالی با مقدار صفر)

| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شماره یکتای سند انبار |
| `transaction_type` | Enum(`IN`, `OUT`) | Not Null | نوع سند: `IN` (ورود/رسید) یا `OUT` (خروج/حواله) |
| `transaction_source` | String | Default `INTERNAL_USE`, Nullable | منبع رخداد: `OPENING_BALANCE`, `PURCHASE`, `SALES`, `IN_ADJUSTMENT`, `OUT_ADJUSTMENT`, `PRICE_ADJUSTMENT`, `TRANSFER`, `BAGGING`, `CUTTING`, `STOCKTAKING`, `RETURN`, `INTERNAL_USE` |
| `product_id` | Integer | FK `products.id`, Not Null | کالای موضوع سند |
| `warehouse_id` | Integer | FK `warehouses.id`, Not Null | انبار محل استقرار |
| `quantity` | Float | Not Null | مقدار بر مبنای واحد سنجش اصلی |
| `secondary_quantity` | Float | Nullable | مقدار فرعی (تعداد شاخه، بندیل، کیسه) |
| `secondary_uom` | String | Nullable | واحد فرعی کالا |
| `unit_price` | Float | Nullable, Default 0.0 | فی واحد جهت کاردکس ریالی |
| `batch_number` | String | Nullable | شماره بهر یا پارت تولیدی |
| `reference_document` | String | Nullable | شماره سفارش، بارنامه یا قبض |
| `created_at` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت سیستمی |
| `transaction_date` | DateTime(tz=True) | Server Default func.now() | تاریخ موثر رخداد تجاری |
| `fiscal_year_id` | Integer | FK `fiscal_years.id`, Nullable | سال مالی منتسب به سند |
| `status` | Enum(`DocumentStatus`) | Not Null, Default `APPROVED` | وضعیت سند: `DRAFT`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `CANCELLED` |
| `rejection_reason` | String | Nullable | دلیل رد سند در کارتابل |
| `approved_by_id` | Integer | FK `users.id`, Nullable | سرپرست تأییدکننده نهایی |
| `approved_at` | DateTime(tz=True) | Nullable | زمان تأیید نهایی و اثرگذاری در موجودی |
| `is_return` | Boolean | Default False | نشانگر سند مرجوعی |
| `return_reason` | String | Nullable | علت مرجوعی کالا |
| `parent_transaction_id`| Integer | FK `stock_transactions.id`, Nullable | عطف به سند اصلی مرجع |
| `weight_per_unit` | Float | Nullable | میانگین وزن هر شاخه/بندیل |
| `standard_weight` | Float | Nullable | وزن استاندارد اشتال |
| `deviation_percent` | Float | Nullable | درصد انحراف خط نورد |
| `freight_cost` | Float | Default 0.0 | کرایه ناخالص حمل بارنامه |
| `insurance_cost` | Float | Default 0.0 | هزینه بیمه حمل |
| `weighbridge_cost` | Float | Default 0.0 | تعرفه باسکول دیجیتال |
| `bill_of_lading_qty` | Float | Nullable | تناژ مبدأ قیدشده در بارنامه |
| `shrinkage_qty` | Float | Nullable | کسری وزن مسیر حمل |
| `shrinkage_percent` | Float | Nullable | درصد افت بار |
| `allowed_tolerance_percent`| Float | Default 0.3 | سقف افت مجاز باربری (۰.۳٪) |
| `penalty_amount` | Float | Default 0.0 | جریمه کسر بار مازاد کسرشده از کرایه |
| `total_landed_cost` | Float | Default 0.0 | بهای تمام‌شده تجمیعی تحویل انبار |
| `heat_number` | String | Nullable | شماره ذوب متالورژی |
| `mtc_number` | String | Nullable | شماره شناسنامه MTC آزمایشگاه |
| `chemical_analysis` | String | Nullable | آنالیز عناصر شیمیایی |
| `mechanical_analysis` | String | Nullable | آزمون مقاومت کششی و تسلیم |
| `chemical_nitrogen` | Float | Nullable | درصد ازت کود اوره |
| `chemical_biuret` | Float | Nullable | درصد بیورت اوره |
| `chemical_moisture` | Float | Nullable | درصد رطوبت اوره |
| `waybill_number` | String | Nullable | شماره بارنامه راهداری |
| `tracking_code` | String | Nullable | کد رهگیری سامانه تجارت |
| `created_by_id` | Integer | FK `users.id`, Nullable | کاربر ثبت‌کننده سند |
| `supplier_id` | Integer | FK `suppliers.id`, Nullable | طرف حساب تأمین‌کننده |
| `customer_id` | Integer | FK `customers.id`, Nullable | طرف حساب مشتری |
| `purchase_order_id` | Integer | FK `purchase_orders.id`, Nullable | سفارش خرید مرتبط |
| `purchase_order_item_id` | Integer | FK `purchase_order_items.id`, Nullable | ردیف سفارش خرید |
| `sales_order_id` | Integer | FK `sales_orders.id`, Nullable | سفارش فروش مرتبط |
| `sales_order_item_id` | Integer | FK `sales_order_items.id`, Nullable | ردیف سفارش فروش |
| `weighbridge_ticket_id` | Integer | FK `weighbridge_tickets.id`, Nullable | قبض باسکول متصل |

### ۱.۱۱. جدول `purchase_orders` (سفارشات خرید - PO)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه یکتای سفارش خرید |
| `po_number` | String | Unique, Index, Not Null | شماره سفارش خرید (مانند `PO-1403-0001`) |
| `supplier_id` | Integer | FK `suppliers.id`, Not Null | تأمین‌کننده طرف قرارداد |
| `order_date` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت سفارش |
| `delivery_due_date` | String | Nullable | موعد تحویل کالا |
| `status` | Enum(`PurchaseOrderStatus`)| Not Null, Default `CONFIRMED` | وضعیت: `DRAFT`, `CONFIRMED`, `PARTIALLY_RECEIVED`, `COMPLETED`, `CANCELLED` |
| `notes` | String | Nullable | شرایط قرارداد بازرگانی |
| `subtotal_amount` | Float | Default 0.0 | مبلغ پایه بدون مالیات (Matrah) |
| `vat_rate` | Float | Default 0.10 | نرخ مالیات ارزش افزوده (۱۰٪ یا ۲۰٪) |
| `vat_amount` | Float | Default 0.0 | کل مالیات بر ارزش افزوده |
| `tevkifat_rate` | String | Nullable | نسبت توقیف مالیات آهن‌آلات (مانند `4/10`) |
| `tevkifat_amount` | Float | Default 0.0 | مبلغ توقیف مالیات پرداختی به دارایی |
| `total_amount` | Float | Default 0.0 | مبلغ قابل پرداخت به فروشنده |
| `currency` | String | Default "IRR" | واحد ارزی (IRR یا TRY) |
| `created_by_id` | Integer | FK `users.id`, Nullable | کاربر ثبت‌کننده سفارش |
| `created_at` | DateTime(tz=True) | Server Default func.now() | زمان ثبت |

### ۱.۱۲. جدول `purchase_order_items` (اقلام سفارش خرید)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه ردیف قلم کالا |
| `purchase_order_id` | Integer | FK `purchase_orders.id` (CASCADE), Not Null | سربرگ سفارش خرید |
| `product_id` | Integer | FK `products.id`, Not Null | شناسه کالای خریداری‌شده |
| `quantity` | Float | Not Null | مقدار سفارش‌شده |
| `received_quantity` | Float | Default 0.0 | مقدار قطعی رسیدشده در انبار |
| `unit_price` | Float | Default 0.0 | فی واحد خرید |
| `total_price` | Float | Default 0.0 | مبلغ ردیف (`quantity * unit_price`) |

### ۱.۱۳. جدول `sales_orders` (سفارشات فروش - SO)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه یکتای سفارش فروش |
| `so_number` | String | Unique, Index, Not Null | شماره سفارش فروش (مانند `SO-1403-0001`) |
| `customer_id` | Integer | FK `customers.id`, Not Null | خریدار / کارفرما |
| `order_date` | DateTime(tz=True) | Server Default func.now() | تاریخ ثبت سفارش فروش |
| `delivery_due_date` | String | Nullable | موعد تحویل به خریدار |
| `status` | Enum(`SalesOrderStatus`) | Not Null, Default `CONFIRMED` | وضعیت: `CONFIRMED`, `PARTIALLY_DELIVERED`, `COMPLETED`, `CANCELLED` |
| `notes` | String | Nullable | شرایط قرارداد فروش |
| `subtotal_amount` | Float | Default 0.0 | مبلغ پایه پیش از مالیات |
| `vat_rate` | Float | Default 0.10 | نرخ مالیات ارزش افزوده |
| `vat_amount` | Float | Default 0.0 | کل مالیات بر ارزش افزوده |
| `tevkifat_rate` | String | Nullable | نسبت کسر توقیف مالیات آهن‌آلات |
| `tevkifat_amount` | Float | Default 0.0 | مبلغ توقیف مالیات |
| `total_amount` | Float | Default 0.0 | کل مبلغ دریافتی از مشتری |
| `currency` | String | Default "IRR" | واحد ارزی قرارداد |
| `created_by_id` | Integer | FK `users.id`, Nullable | کاربر صادرکننده پیش‌فاکتور |
| `created_at` | DateTime(tz=True) | Server Default func.now() | زمان ثبت |

### ۱.۱۴. جدول `sales_order_items` (اقلام سفارش فروش)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه ردیف کالا در فروش |
| `sales_order_id` | Integer | FK `sales_orders.id` (CASCADE), Not Null | سربرگ سفارش فروش |
| `product_id` | Integer | FK `products.id`, Not Null | کالای فروخته‌شده |
| `quantity` | Float | Not Null | مقدار فروخته‌شده |
| `delivered_quantity` | Float | Default 0.0 | مقدار قطعی تحویل‌شده و خروج از انبار |
| `unit_price` | Float | Default 0.0 | فی واحد فروش |
| `total_price` | Float | Default 0.0 | مبلغ ردیف فروش |

### ۱.۱۵. جدول `weighbridge_tickets` (قبوض باسکول دیجیتال تریلی)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه قبض باسکول |
| `ticket_number` | String | Unique, Index, Not Null | شماره قبض نوبت باسکول |
| `truck_plate` | String | Not Null | پلاک خودروی سنگین |
| `driver_name` | String | Not Null | نام راننده تریلی |
| `driver_phone` | String | Nullable | شماره تماس راننده |
| `truck_type` | String | Default "تریلی کفی ۱۸ چرخ" | تیپ خودرو سنگین |
| `supplier_id` | Integer | FK `suppliers.id`, Nullable | تأمین‌کننده (بارهای ورودی) |
| `customer_id` | Integer | FK `customers.id`, Nullable | مشتری (بارهای خروجی) |
| `purchase_order_id` | Integer | FK `purchase_orders.id`, Nullable | سفارش خرید متصل |
| `sales_order_id` | Integer | FK `sales_orders.id`, Nullable | سفارش فروش متصل |
| `product_id` | Integer | FK `products.id`, Not Null | کالای در حال حمل |
| `warehouse_id` | Integer | FK `warehouses.id`, Not Null | انبار بارگیری/تخلیه |
| `gross_weight` | Float | Nullable, Default 0.0 | وزن ناخالص (پر) به کیلوگرم |
| `tare_weight` | Float | Nullable, Default 0.0 | وزن خالی (تار) به کیلوگرم |
| `net_weight` | Float | Nullable, Default 0.0 | وزن خالص بار (`gross - tare`) |
| `max_allowed_weight`| Float | Default 40000.0 | حداکثر تناژ مجاز جاده‌ای (KGM) |
| `is_overweight` | Boolean | Default False | هشدار اضافه تناژ غیرمجاز |
| `status` | Enum(`WeighbridgeStatus`) | Default `FIRST_WEIGHING` | وضعیت: `FIRST_WEIGHING`, `COMPLETED`, `CANCELLED` |
| `notes` | String | Nullable | توضیحات باسکول‌چی |
| `operator_name` | String | Nullable | متصدی شیفت باسکول |
| `stock_transaction_id`| Integer | FK `stock_transactions.id`, Nullable | سند انبار منتسب به این قبض |
| `created_at` | DateTime(tz=True) | Server Default func.now() | زمان توزین اول |
| `completed_at` | DateTime(tz=True) | Nullable | زمان توزین دوم |

### ۱.۱۶. جدول `cutting_orders` (دستورات برش آهن و مدیریت ته‌شاخه)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه دستور برش |
| `order_number` | String | Unique, Index, Not Null | شماره دستور برش |
| `product_id` | Integer | FK `products.id`, Not Null | پروفیل مادر جهت برش |
| `original_length` | Float | Default 12.0 | طول اولیه شاخه به متر |
| `cut_length` | Float | Not Null | طول قطعه برش‌خورده تحویلی |
| `pieces_count` | Integer | Default 1 | تعداد قطعات برش |
| `remnant_length` | Float | Not Null | طول باقیمانده ته‌شاخه به متر |
| `remnant_weight` | Float | Default 0.0 | وزن ته‌شاخه (کیلوگرم) |
| `destination` | String | Default "انبار ته‌شاخه‌ها" | انبار مقصد قطعه (ضایعات یا ته‌شاخه) |
| `status` | Enum(`CuttingStatus`) | Default `COMPLETED` | وضعیت عملیات برش |
| `notes` | String | Nullable | توضیحات کارگاه |
| `created_at` | DateTime(tz=True) | Server Default func.now() | زمان ثبت |

### ۱.۱۷. جدول `bagging_orders` (کیسه‌گیری فله اوره به جامبوبگ)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه عملیات کیسه‌گیری |
| `order_number` | String | Unique, Index, Not Null | شماره دستور کیسه‌گیری |
| `bulk_product_id` | Integer | FK `products.id`, Not Null | کالای فله مصرفی (اوره فله صنعتی) |
| `packaged_product_id`| Integer | FK `products.id`, Not Null | کالای تولیدی (جامبوبگ ۱ تنی) |
| `bulk_tonnage_used` | Float | Not Null | تناژ فله کسرشده از انبار (تن) |
| `packages_produced` | Float | Not Null | تعداد کیسه/جامبوبگ تولیدشده |
| `package_type` | String | Default "جامبوبگ ۱ تنی" | نوع بسته‌بندی |
| `waste_tonnage` | Float | Default 0.0 | پرتی و غبار خط کیسه‌گیری (تن) |
| `packaging_cost_per_ton`| Float | Default 0.0 | هزینه دستمزد و بسته‌بندی هر تن |
| `status` | Enum(`BaggingStatus`) | Default `COMPLETED` | وضعیت عملیات |
| `notes` | String | Nullable | توضیحات |
| `created_at` | DateTime(tz=True) | Server Default func.now() | زمان ثبت |

### ۱.۱۸. جدول `audit_logs` (لاگ حسابرسی و ردپای امنیتی)
| نام ستون | نوع داده | کلید / محدودیت | توضیحات |
| :--- | :--- | :--- | :--- |
| `id` | Integer | PK, Index | شناسه لاگ |
| `user_id` | Integer | FK `users.id`, Nullable | کاربر مجری |
| `user_name` | String | Nullable | نام کاربر |
| `action` | String | Not Null | عمل: `CREATE`, `UPDATE`, `APPROVE`, `REJECT`, `CANCEL`, `CLOSE_FISCAL_YEAR` |
| `entity_name` | String | Not Null | موجودیت هدف: `StockTransaction`, `PurchaseOrder`, `SalesOrder`, `FiscalYear` |
| `entity_id` | String | Nullable | شناسه کلید اصلی موجودیت |
| `details` | String | Nullable | متن و جزئیات دقیق تغییرات |
| `ip_address` | String | Nullable | نشانی IP |
| `created_at` | DateTime(tz=True) | Server Default func.now() | زمان دقیق رخداد |

---

## ۲. گردش کار سفارش و انبار (Order & Inventory Flow)

### ۲.۱. چرخه خرید، انبار و باسکول (Inbound Flow)

```
[ثبت سفارش خرید PO] ──► وضعیت: CONFIRMED (بدون هیچ اثری بر موجودی انبار)
           │
           ├─► ورود محموله و ثبت نوبت در باسکول (FIRST_WEIGHING)
           │
           ├─► ثبت تخلیه در خرید (receive_purchase_order):
           │     └─► ایجاد سند IN با وضعیت PENDING_APPROVAL در کارتابل انبار
           │     └─► موجودی کالا و received_quantity هنوز تغییری نکرده‌اند.
           │
           ├─► تخلیه کامل بار و توزین دوم باسکول (complete_second_weighing):
           │     ├─► محاسبه وزن خالص (کیلوگرم به تن در صورت uom="تن")
           │     ├─► بررسی سند PENDING_APPROVAL متصل به سفارش در کارتابل
           │     └─► آپدیت همان سند کارتابل با وزن باسکول (جلوگیری از صدور سند دوبل)
           │
           └─► تایید نهایی سرپرست انبار در کارتابل (approve_transaction):
                 ├─► سند انبار وضعیت APPROVED می‌گیرد.
                 ├─► موجودی فیزیکی و کاردکس انبار شارژ می‌شود.
                 ├─► مقدار received_quantity در اقلام سفارش خرید افزایش می‌یابد.
                 └─► وضعیت سفارش به COMPLETED یا PARTIALLY_RECEIVED تبدیل می‌شود.
```

### ۲.۲. چرخه فروش، انبار و تحویل (Outbound Flow)

```
[ثبت سفارش فروش SO] ──► وضعیت: CONFIRMED (بدون تغییر موجودی فیزیکی)
           │
           ├─► صدور حواله خروج (deliver_sales_order):
           │     ├─► کنترل سقف ۵٪ تلورانس سفارش نسبت به delivered_quantity
           │     ├─► کنترل موجودی آزاد (Available Stock = Approved In - Approved Out - Pending Out)
           │     ├─► استخراج فی میانگین موزون جهت کاردکس ریالی
           │     └─► ایجاد سند OUT با وضعیت PENDING_APPROVAL در کارتابل انبار
           │         (این سند بلافاصله از موجودی آزاد کسر و رزرو می‌شود تا فروش همزمان رخ ندهد)
           │
           └─► تایید نهایی سرپرست انبار در کارتابل (approve_transaction):
                 ├─► سند خروج به APPROVED تبدیل می‌شود.
                 ├─► موجودی فیزیکی انبار کسر می‌گردد.
                 ├─► مقدار delivered_quantity در سفارش فروش افزایش می‌یابد.
                 └─► وضعیت سفارش فروش به COMPLETED یا PARTIALLY_DELIVERED تبدیل می‌شود.
```

### ۲.۳. موتور محاسبه موجودی فیزیکی، آزاد و فی میانگین موزون

1. **موجودی فیزیکی قطعی (`get_current_stock`):**
   تنها اسناد تاییدشده (`APPROVED`) مبنای کاردکس و موجودی انبار هستند:
   $$\text{Current Physical Stock} = \sum (\text{IN}_{\text{APPROVED}}) - \sum (\text{OUT}_{\text{APPROVED}})$$

2. **موجودی آزاد و قابل تخصیص (`get_available_stock`):**
   جهت جلوگیری از فروش همزمان یک کالا توسط دو کارشناس فروش، اسناد خروجی در کارتابل (`PENDING_APPROVAL`) به عنوان موجودی رزروشده در نظر گرفته می‌شوند:
   $$\text{Available Stock} = \sum (\text{IN}_{\text{APPROVED}}) - \left[ \sum (\text{OUT}_{\text{APPROVED}}) + \sum (\text{OUT}_{\text{PENDING\_APPROVAL}}) \right]$$

3. **فی میانگین موزون متحرک لحظه‌ای (`get_weighted_average_cost`):**
   در هر ورود با نرخ جدید، نرخ میانگین تجدید محاسبه شده و در خروجی‌ها حفظ می‌شود:
   $$\text{New Average Rate} = \frac{(\text{Current Qty} \times \text{Current Rate}) + (\text{Inflow Qty} \times \text{Inflow Cost})}{\text{Current Qty} + \text{Inflow Qty}}$$

### ۲.۴. موتور اسناد اصلاحیه ورودی و خروجی (Adjustments Engine)

در مسیر `POST /inventory/transactions/{tx_id}/adjust`، کاربر سند قطعی (`APPROVED`) را با مقادیر و فی جدید اصلاح می‌کند. سیستم به جای ویرایش رکوردهای تاریخی، مابه‌التفاوت مقداری را محاسبه می‌نماید:
$$\Delta Q = Q_{\text{new}} - Q_{\text{old}}$$

- **اصلاحیه سند ورودی (`IN`):**
  - $\Delta Q > 0$: صدور سند افزایشی ورود (`TransactionType.IN`, `source=IN_ADJUSTMENT`) به مقدار $\Delta Q$ و افزایش `received_quantity` سفارش خرید.
  - $\Delta Q < 0$: کنترل عدم منفی شدن موجودی لحظه‌ای انبار، صدور سند کاهشی خروج (`TransactionType.OUT`, `source=IN_ADJUSTMENT`) به مقدار $|\Delta Q|$ و کسر از `received_quantity` سفارش خرید.
- **اصلاحیه سند خروجی (`OUT`):**
  - $\Delta Q > 0$: کنترل کفایت موجودی آزاد انبار، صدور سند خروج تکمیلی (`TransactionType.OUT`, `source=OUT_ADJUSTMENT`) و افزایش `delivered_quantity` سفارش فروش.
  - $\Delta Q < 0$: صدور سند ورود بازگشت به انبار (`TransactionType.IN`, `source=OUT_ADJUSTMENT`) با فی میانگین موزون سند مرجع و کسر از `delivered_quantity` سفارش فروش.
- **اصلاحیه ریالی (بهای تمام‌شده):**
  اگر $\Delta Q = 0$ بوده ولی فی واحد یا هزینه حمل تغییر کند، سند اصلاحیه ریالی (`source=PRICE_ADJUSTMENT`) با مقدار ۰.۰ و نرخ جدید ثبت شده و در کاردکس ریالی اعمال می‌شود.

### ۲.۵. بستن سال مالی و انتقال مانده‌ها (Fiscal Year Closing)

در مسیر `POST /inventory/fiscal-year-close`:
1. **ارزیابی سلامت پیش از بستن:** عدم وجود سند معلق (`PENDING_APPROVAL`) در کارتابل و عدم وجود قبض باسکول نیمه‌کاره در فاز اول توزین (`FIRST_WEIGHING`).
2. **پالایش اقلام راکد و صفر:** هر کالایی که مانده آن در انبار $\le 0.0001$ باشد، به دوره مالی جدید منتقل نمی‌شود.
3. **افتتاحیه دوره جدید:** صدور سند ورود با وضعیت `APPROVED` و منبع `OPENING_BALANCE` با مانده اصلی، مانده فرعی (شاخه/بندیل) و آخرین فی میانگین موزون پایان سال قبل، و بستن قطعی سال قبلی (`is_closed=True`).

### ۲.۶. تحلیل نقاط ثبت تکراری و راهکارهای مهارشده در کدها

| سناریوی ریسک تکراری | نحوه رخداد در سیستم‌های سنتی | سازوکار مهار و کنترل در کد فعلی |
| :--- | :--- | :--- |
| **کلیک چندباره در تخلیه سفارش** | ارسال همزمان چند درخواست HTTP در زمان کندی شبکه | صدور سند در وضعیت موقت `PENDING_APPROVAL` و امکان ابطال یا حذف توسط سرپرست انبار در کارتابل |
| **ثبت مضاعف سفارش و باسکول** | ثبت رسید از طرف کارشناس بازرگانی و همزمان ثبت سند توسط باسکول‌چی | متد `complete_second_weighing` ابتدا کارتابل را جستجو می‌کند؛ در صورت وجود سند معلق، همان سند را با وزن باسکول آپدیت می‌کند و سند جدید نمی‌سازد. اگر قبلاً سند صادر شده باشد، خطای صریح ۴۰۰ برمی‌گرداند. |
| **دریافت مازاد بر سفارش** | دریافت بارهایی بیشتر از ظرفیت قرارداد | محدودیت سقف دریافت در `receive_purchase_order` و تحویل در `deliver_sales_order` تا حداکثر ۵٪ سقف تلورانس توزین باسکول. |
| **فروش همزمان موجودی واحد** | دو کاربر همزمان یک موجودی را در دو فاکتور بفروشند | متد `get_available_stock` اسناد منتظر تایید را کسر می‌کند و قبل از صدور سند، مانده آزاد را بررسی می‌نماید. |
| **مرجوعی بیش از مقدار خرید/فروش** | صدور چندباره سند برگشت برای یک فاکتور | کنترل سقف تجمیعی مرجوعی‌ها در `process_return_transaction` به طوری که مجموع مرجوعی‌ها نمی‌تواند از مقدار تحویل‌شده سند اصلی تجاوز کند. |

---

## ۳. فهرست کامل APIها و توابع اصلی منطق تجاری (Endpoints & Core Functions)

| نام فایل | نام تابع / روت | ورودی‌ها | شرح عملکرد منطقی و تجاری |
| :--- | :--- | :--- | :--- |
| `src/services/inventory_service.py` | `calculate_stock_balances` | `db: Session` | محاسبه ماتریسی مانده مقداری و دو واحدی تمام کالاها در تمام انبارها صرفاً بر مبنای اسناد `APPROVED`. |
| `src/services/inventory_service.py` | `get_current_stock` | `db, product_id, warehouse_id` | محاسبه موجودی فیزیکی قطعی کالا در انبار با فرمول `Approved IN - Approved OUT`. |
| `src/services/inventory_service.py` | `get_available_stock` | `db, product_id, warehouse_id` | محاسبه موجودی آزاد و قابل تخصیص کالا پس از کسر حواله‌های خروج معلق در کارتابل انبار. |
| `src/services/inventory_service.py` | `get_current_secondary_stock`| `db, product_id, warehouse_id` | محاسبه مانده موجودی واحد فرعی (شاخه، بندیل، کیسه) در انبار انتخابی. |
| `src/services/inventory_service.py` | `get_weighted_average_cost` | `db, product_id, warehouse_id` | محاسبه فی میانگین موزون متحرک کالا جهت ارزش‌گذاری خروجی‌ها، حواله‌های انتقال و انبارگردانی. |
| `src/services/tax_service.py` | `calculate_tax` | `base_amount, region_code, is_steel, custom_vat_rate, tevkifat_ratio, steel_base_amount` | محاسبه ارزش افزوده ایران (۱۰٪) و ترکیه (۲۰٪) و اعمال توقیف ۴/۱۰ آهن‌آلات صرفاً روی بهای اقلام فولادی. |
| `src/services/tax_service.py` | `is_steel_tevkifat_eligible` | `gtip_code, category_code, product_name` | بررسی شمولیت کالا در نظام توقیف مالیات آهن و فولاد ترکیه بر اساس فصول ۷۲ و ۷۳ تعرفه گمرکی. |
| `src/services/audit_service.py` | `log` | `db, action, entity_name, entity_id, user_id, details` | ثبت تراکنشی وقایع در جدول `audit_logs` به منظور پایش و زنجیره حسابرسی مالی. |
| `src/api/purchases_ui.py` | `create_purchase_order`<br>`POST /purchases` | `po_number, supplier_id, delivery_due_date, items[]` | ثبت سفارش خرید جدید، تفکیک ردیف‌های فولادی، محاسبه مالیات و توقیف و ایجاد رکورد با وضعیت `CONFIRMED`. |
| `src/api/purchases_ui.py` | `receive_purchase_order`<br>`POST /purchases/{id}/receive`| `order_id, warehouse_id, item_id[], receive_qty[]` | کنترل سقف ۵٪ تلورانس باسکول و صدور سند `IN` در وضعیت `PENDING_APPROVAL` در کارتابل بدون تغییر در موجودی. |
| `src/api/sales_ui.py` | `create_sales_order`<br>`POST /sales` | `so_number, customer_id, delivery_due_date, items[]` | ثبت سفارش فروش جدید، تفکیک اقلام فولادی، محاسبه مالیات و توقیف و ایجاد رکورد با وضعیت `CONFIRMED`. |
| `src/api/sales_ui.py` | `deliver_sales_order`<br>`POST /sales/{id}/deliver` | `order_id, warehouse_id, item_id[], deliver_qty[]` | کنترل موجودی آزاد کالا، استخراج فی میانگین موزون و صدور سند `OUT` با وضعیت `PENDING_APPROVAL` در کارتابل. |
| `src/api/inventory_ui.py` | `process_transaction`<br>`POST /inventory/transaction` | `transaction_type, product_id, warehouse_id, quantity, po_id, so_id, ...` | قفل ثبت دستی مستقیم خرید/فروش بدون شماره PO/SO، کنترل موجودی آزاد و ثبت رسید/حواله مستقیم. |
| `src/api/inventory_ui.py` | `approve_transaction`<br>`POST /inventory/transactions/{id}/approve` | `tx_id, db, current_user` | **منبع انحصاری اثرگذاری بر موجودی:** تغییر وضعیت سند به `APPROVED`، افزایش/کاهش موجودی، و آپدیت `received_qty` یا `delivered_qty`. |
| `src/api/inventory_ui.py` | `reject_transaction`<br>`POST /inventory/transactions/{id}/reject` | `tx_id, rejection_reason` | رد سند معلق در کارتابل و درج دلیل رسمی رد در پرونده سند. |
| `src/api/inventory_ui.py` | `cancel_transaction`<br>`POST /inventory/transactions/{id}/cancel` | `tx_id, db, current_user` | ابطال سند انبار و خارج کردن آن از گردش حسابداری. |
| `src/api/inventory_ui.py` | `adjust_transaction`<br>`POST /inventory/transactions/{id}/adjust` | `tx_id, new_quantity, new_secondary_qty, new_unit_price, adjustment_reason` | موتور اسناد اصلاحیه ورودی و خروجی با محاسبه مابه‌التفاوت مقداری $\Delta Q$ و به‌روزرسانی مانده سفارشات. |
| `src/api/inventory_ui.py` | `process_transfer`<br>`POST /inventory/transfer` | `product_id, from_wh, to_wh, quantity, secondary_qty` | انتقال بین انبارها: کنترل موجودی مبدأ، صدور همزمان سند خروج با نرخ میانگین موزون و ورود به مقصد با حفظ واحد فرعی. |
| `src/api/inventory_ui.py` | `process_stocktaking`<br>`POST /inventory/stocktaking` | `warehouse_id, counted_qty[], ...` | مغایرت‌گیری انبارگردانی: مقایسه فیزیکی با سیستم و صدور خودکار اسناد تعدیل مثبت یا کسری با فی میانگین موزون. |
| `src/api/inventory_ui.py` | `process_return_transaction`<br>`POST /inventory/returns` | `parent_transaction_id, quantity, secondary_qty, return_reason` | مرجوعی از خرید یا فروش: کنترل سقف مرجوعی، حفظ واحد فرعی و صدور سند معکوس با پرچم `is_return=True`. |
| `src/api/inventory_ui.py` | `close_fiscal_year`<br>`POST /inventory/fiscal-year-close` | `new_year_name, start_date, end_date` | کنترل نبود اسناد معلق، حذف موجودی‌های صفر، صدور سند `OPENING_BALANCE` در سال جدید و قفل سال قدیم. |
| `src/api/weighbridge_ui.py` | `create_weighbridge_ticket`<br>`POST /weighbridge` | `ticket_number, truck_plate, driver_name, initial_weight, po_id, so_id` | ثبت نوبت و توزین اول محموله و اعتبارسنجی سقف وزن ناخالص مجاز جاده‌ای (پلیس‌راه / KGM). |
| `src/api/weighbridge_ui.py` | `complete_second_weighing`<br>`POST /weighbridge/{id}/complete` | `ticket_id, second_weight, auto_create_transaction` | ثبت توزین دوم، محاسبه وزن خالص، تبدیل کیلوگرم به تن و آپدیت سند معلق کارتابل (حذف ثبت دوبل). |
| `src/api/cutting_ui.py` | `create_cutting_order`<br>`POST /cutting` | `order_number, product_id, original_length, cut_length, pieces_count` | ثبت دستور برش، محاسبه متراژ و وزن ته‌شاخه و صدور خودکار سند خروج شاخه مادر و ورود ته‌شاخه به کاردکس. |
| `src/api/bagging_ui.py` | `create_bagging_order`<br>`POST /bagging` | `order_number, bulk_product_id, packaged_product_id, bulk_tonnage, packages` | کیسه‌گیری فله به جامبوبگ اوره: کسر فله از انبار با سند `OUT` و افزودن محصول بسته‌بندی با سند `IN` با احتساب پرتی. |
| `src/api/stock_api.py` | `get_stock`<br>`GET /api/stock` | `product_id, warehouse_id` | وب‌سرویس Ajax برای استعلام برخط موجودی انبار انتخابی در فرم‌های ورود اطلاعات. |

---

## ۴. کدهای حساس پایتون (Critical Code Snippets)

در این بخش، کدهای دقیق پایتون مربوط به ثبت سفارشات، گردش کارتابل، تاییدیه، اسناد اصلاحیه، پایان سال مالی و محاسبات موجودی عیناً بدون تغییر درج شده است:

### ۴.۱. ثبت سفارش خرید و تخلیه به کارتابل انبار (`src/api/purchases_ui.py`)

```python
@router.post("", response_class=HTMLResponse)
async def create_purchase_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    po_number: str = Form(...),
    supplier_id: int = Form(...),
    delivery_due_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    product_id: list[int] = Form(...),
    quantity: list[float] = Form(...),
    unit_price: list[float] = Form(...)
):
    """ذخیره سفارش خرید و اقلام مربوطه با محاسبه خودکار مالیات و توقیف آهن‌آلات"""
    try:
        supplier = db.query(Supplier).filter(Supplier.id == supplier_id).first()
        is_tr = (supplier and supplier.country_code == "TR") or (request.cookies.get("nexus_region", "IR").upper() == "TR")
        region_code = "TR" if is_tr else "IR"

        subtotal = 0.0
        steel_subtotal = 0.0
        has_steel = False
        valid_items_data = []

        for pid, qty, price in zip(product_id, quantity, unit_price):
            if qty > 0:
                line_total = qty * price
                subtotal += line_total
                p = db.query(Product).options(joinedload(Product.category)).filter(Product.id == pid).first()
                if p and TaxService.is_steel_tevkifat_eligible(
                    gtip_code=p.gtip_code,
                    category_code=p.category.code if p.category else None,
                    product_name=p.name
                ):
                    has_steel = True
                    steel_subtotal += line_total
                valid_items_data.append((pid, qty, price, line_total))

        tax_res = TaxService.calculate_tax(
            base_amount=subtotal,
            region_code=region_code,
            is_steel=has_steel,
            steel_base_amount=steel_subtotal
        )

        po = PurchaseOrder(
            po_number=po_number.strip(),
            supplier_id=supplier_id,
            delivery_due_date=delivery_due_date.strip() if delivery_due_date else None,
            status=PurchaseOrderStatus.CONFIRMED,
            notes=notes.strip() if notes else None,
            subtotal_amount=tax_res.base_amount,
            vat_rate=tax_res.vat_rate,
            vat_amount=tax_res.vat_amount,
            tevkifat_rate=tax_res.tevkifat_rate_str,
            tevkifat_amount=tax_res.tevkifat_amount,
            total_amount=tax_res.total_payable,
            currency="TRY" if is_tr else "IRR",
            created_by_id=current_user.id
        )
        db.add(po)
        db.flush()

        for pid, qty, price, line_total in valid_items_data:
            item = PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=pid,
                quantity=qty,
                received_quantity=0.0,
                unit_price=price,
                total_price=line_total
            )
            db.add(item)

        db.commit()
        return RedirectResponse(
            url=f"/purchases/{po.id}?msg=" + quote(f"سفارش خرید {po.po_number} با موفقیت ثبت گردید"),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise


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
        created_receipts = 0
        for it_id, r_qty in zip(item_id, receive_qty):
            if r_qty > 0:
                item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == it_id).first()
                if item:
                    # کنترل سقف ۵٪ تلورانس باسکول نسبت به مقدار سفارش
                    max_allowed_receive = (item.quantity * 1.05) - item.received_quantity
                    if r_qty > max_allowed_receive:
                        raise HTTPException(
                            status_code=400,
                            detail=f"مقدار دریافتی برای قلم {item.product.name} ({r_qty}) بیش از سقف مجاز سفارش به همراه ۵٪ تلورانس باسکول است."
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
                        created_by_id=current_user.id
                    )
                    db.add(tx)
                    created_receipts += 1

        db.commit()
        return RedirectResponse(
            url=f"/purchases/{po.id}?msg=" + quote(f"رسید موقت انبار صادر شد و جهت تایید نهایی و اعمال در موجودی به کارتابل انبار ارسال گردید."),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise
```

---

### ۴.۲. ثبت سفارش فروش و حواله خروج به کارتابل انبار (`src/api/sales_ui.py`)

```python
@router.post("", response_class=HTMLResponse)
async def create_sales_order(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    so_number: str = Form(...),
    customer_id: int = Form(...),
    delivery_due_date: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    product_id: list[int] = Form(...),
    quantity: list[float] = Form(...),
    unit_price: list[float] = Form(...)
):
    """ثبت و ذخیره سفارش فروش با تفکیک توقیف مالیاتی آهن‌آلات"""
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        is_tr = (customer and customer.country_code == "TR") or (request.cookies.get("nexus_region", "IR").upper() == "TR")
        region_code = "TR" if is_tr else "IR"

        subtotal = 0.0
        steel_subtotal = 0.0
        has_steel = False
        valid_items_data = []

        for pid, qty, price in zip(product_id, quantity, unit_price):
            if qty > 0:
                line_total = qty * price
                subtotal += line_total
                p = db.query(Product).options(joinedload(Product.category)).filter(Product.id == pid).first()
                if p and TaxService.is_steel_tevkifat_eligible(
                    gtip_code=p.gtip_code,
                    category_code=p.category.code if p.category else None,
                    product_name=p.name
                ):
                    has_steel = True
                    steel_subtotal += line_total
                valid_items_data.append((pid, qty, price, line_total))

        tax_res = TaxService.calculate_tax(
            base_amount=subtotal,
            region_code=region_code,
            is_steel=has_steel,
            steel_base_amount=steel_subtotal
        )

        so = SalesOrder(
            so_number=so_number.strip(),
            customer_id=customer_id,
            delivery_due_date=delivery_due_date.strip() if delivery_due_date else None,
            status=SalesOrderStatus.CONFIRMED,
            notes=notes.strip() if notes else None,
            subtotal_amount=tax_res.base_amount,
            vat_rate=tax_res.vat_rate,
            vat_amount=tax_res.vat_amount,
            tevkifat_rate=tax_res.tevkifat_rate_str,
            tevkifat_amount=tax_res.tevkifat_amount,
            total_amount=tax_res.total_payable,
            currency="TRY" if is_tr else "IRR",
            created_by_id=current_user.id
        )
        db.add(so)
        db.flush()

        for pid, qty, price, line_total in valid_items_data:
            item = SalesOrderItem(
                sales_order_id=so.id,
                product_id=pid,
                quantity=qty,
                delivered_quantity=0.0,
                unit_price=price,
                total_price=line_total
            )
            db.add(item)

        db.commit()
        return RedirectResponse(
            url=f"/sales/{so.id}?msg=" + quote(f"پیش‌فاکتور / سفارش فروش {so.so_number} با موفقیت صادر گردید"),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise


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
        created_count = 0
        for it_id, d_qty in zip(item_id, deliver_qty):
            if d_qty > 0:
                item = db.query(SalesOrderItem).filter(SalesOrderItem.id == it_id).first()
                if item:
                    # ۱. بررسی سقف تحویل سفارش
                    remaining_order_qty = (item.quantity * 1.05) - item.delivered_quantity
                    if d_qty > remaining_order_qty:
                        raise HTTPException(
                            status_code=400,
                            detail=f"مقدار تحویلی قلم {item.product.name} ({d_qty}) بیشتر از مانده سفارش به همراه ۵٪ تلورانس است."
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

                    # ۴. صدور سند حواله خروج موقت (PENDING_APPROVAL)
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
                        created_by_id=current_user.id
                    )
                    db.add(tx)
                    created_count += 1

        db.commit()
        return RedirectResponse(
            url=f"/sales/{so.id}?msg=" + quote("حواله خروج موقت صادر شد و جهت تایید نهایی انباردار به کارتابل انبار ارسال گردید."),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise
```

---

### ۴.۳. تایید نهایی در کارتابل انبارداری (`src/api/inventory_ui.py`)

```python
@router.post("/transactions/{tx_id}/approve")
async def approve_transaction(
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """تایید نهایی سند و اعمال در کاردکس موجودی و به‌روزرسانی پیشرفت سفارشات خرید/فروش"""
    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند یافت نشد")
    
    if tx.status == DocumentStatus.APPROVED:
        return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} قبلاً تأیید شده است"), status_code=303)

    # اگر سند خروجی است، کنترل موجودی فیزیکی
    if tx.transaction_type == TransactionType.OUT:
        cur_stock = InventoryService.get_current_stock(db, tx.product_id, tx.warehouse_id)
        if tx.quantity > cur_stock:
            raise HTTPException(status_code=400, detail=f"موجودی انبار ({cur_stock}) برای تایید سند خروج #{tx.id} به مقدار {tx.quantity} کافی نیست!")

    tx.status = DocumentStatus.APPROVED
    tx.approved_by_id = current_user.id
    tx.approved_at = datetime.utcnow()

    # ۱. به‌روزرسانی سفارش خرید مرتبط (received_quantity)
    if tx.purchase_order_id:
        po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
        if po:
            if tx.purchase_order_item_id:
                item = db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == tx.purchase_order_item_id).first()
                if item:
                    item.received_quantity += tx.quantity
            else:
                match_item = next((it for it in po.items if it.product_id == tx.product_id), None)
                if match_item:
                    match_item.received_quantity += tx.quantity
            
            total_ordered = sum(it.quantity for it in po.items)
            total_rcvd = sum(it.received_quantity for it in po.items)
            if total_rcvd >= total_ordered:
                po.status = PurchaseOrderStatus.COMPLETED
            elif total_rcvd > 0:
                po.status = PurchaseOrderStatus.PARTIALLY_RECEIVED

    # ۲. به‌روزرسانی سفارش فروش مرتبط (delivered_quantity)
    if tx.sales_order_id:
        so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
        if so:
            if tx.sales_order_item_id:
                item = db.query(SalesOrderItem).filter(SalesOrderItem.id == tx.sales_order_item_id).first()
                if item:
                    item.delivered_quantity += tx.quantity
            else:
                match_item = next((it for it in so.items if it.product_id == tx.product_id), None)
                if match_item:
                    match_item.delivered_quantity += tx.quantity
            
            total_ordered = sum(it.quantity for it in so.items)
            total_deliv = sum(it.delivered_quantity for it in so.items)
            if total_deliv >= total_ordered:
                so.status = SalesOrderStatus.COMPLETED
            elif total_deliv > 0:
                so.status = SalesOrderStatus.PARTIALLY_DELIVERED

    db.commit()
    return RedirectResponse(url="/inventory/transactions?msg=" + quote(f"سند #{tx.id} با موفقیت تایید نهایی شد"), status_code=303)
```

---

### ۴.۴. ثبت سند اصلاحیه ورودی، خروجی و ریالی (`src/api/inventory_ui.py`)

```python
@router.post("/transactions/{tx_id}/adjust")
async def adjust_transaction(
    tx_id: int,
    request: Request,
    new_quantity: float = Form(...),
    new_secondary_quantity: Optional[float] = Form(None),
    new_unit_price: Optional[float] = Form(None),
    adjustment_reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """ثبت سند اصلاحیه ورودی/خروجی بر مبنای مابه‌التفاوت با سند مرجع"""
    tx = db.query(StockTransaction).filter(StockTransaction.id == tx_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="سند مرجع یافت نشد")
    if tx.status != DocumentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="فقط اسناد تأیید شده (APPROVED) قابل اصلاح هستند.")

    delta_q = round(new_quantity - tx.quantity, 4)
    old_sec = tx.secondary_quantity or 0.0
    delta_sec = round(new_secondary_quantity - old_sec, 2) if new_secondary_quantity is not None else None
    price_to_use = new_unit_price if (new_unit_price is not None and new_unit_price > 0) else tx.unit_price

    active_fy = db.query(FiscalYear).filter(FiscalYear.is_active == True, FiscalYear.is_closed == False).first()
    fy_id = active_fy.id if active_fy else tx.fiscal_year_id

    # ۱. اصلاحیه سند ورودی (IN)
    if tx.transaction_type == TransactionType.IN:
        if delta_q > 0:
            adj_tx = StockTransaction(
                transaction_type=TransactionType.IN,
                transaction_source=TransactionSource.IN_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=delta_q,
                secondary_quantity=delta_sec,
                secondary_uom=tx.secondary_uom,
                unit_price=price_to_use,
                parent_transaction_id=tx.id,
                purchase_order_id=tx.purchase_order_id,
                purchase_order_item_id=tx.purchase_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه افزایشی ورودی عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.utcnow()
            )
            db.add(adj_tx)
            if tx.purchase_order_id:
                po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
                if po:
                    target_item = db.query(PurchaseOrderItem).get(tx.purchase_order_item_id) if tx.purchase_order_item_id else next((it for it in po.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.received_quantity += delta_q

        elif delta_q < 0:
            abs_delta = abs(delta_q)
            cur_stock = InventoryService.get_current_stock(db, tx.product_id, tx.warehouse_id)
            if abs_delta > cur_stock:
                raise HTTPException(status_code=400, detail=f"کاهش {abs_delta} واحدی کالا باعث منفی شدن موجودی انبار می‌شود! (موجودی فعلی: {cur_stock})")
            
            adj_tx = StockTransaction(
                transaction_type=TransactionType.OUT,
                transaction_source=TransactionSource.IN_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=abs_delta,
                secondary_quantity=abs(delta_sec) if delta_sec else None,
                secondary_uom=tx.secondary_uom,
                unit_price=price_to_use,
                parent_transaction_id=tx.id,
                purchase_order_id=tx.purchase_order_id,
                purchase_order_item_id=tx.purchase_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه کاهشی ورودی عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.utcnow()
            )
            db.add(adj_tx)
            if tx.purchase_order_id:
                po = db.query(PurchaseOrder).filter(PurchaseOrder.id == tx.purchase_order_id).first()
                if po:
                    target_item = db.query(PurchaseOrderItem).get(tx.purchase_order_item_id) if tx.purchase_order_item_id else next((it for it in po.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.received_quantity = max(0.0, target_item.received_quantity - abs_delta)

    # ۲. اصلاحیه سند خروجی (OUT)
    elif tx.transaction_type == TransactionType.OUT:
        if delta_q > 0:
            avail_stock = InventoryService.get_available_stock(db, tx.product_id, tx.warehouse_id)
            if delta_q > avail_stock:
                raise HTTPException(status_code=400, detail=f"موجودی آزاد کالا ({avail_stock}) برای خروج اصلاحیه تکمیلی {delta_q} کافی نیست!")
            
            adj_tx = StockTransaction(
                transaction_type=TransactionType.OUT,
                transaction_source=TransactionSource.OUT_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=delta_q,
                secondary_quantity=delta_sec,
                secondary_uom=tx.secondary_uom,
                unit_price=price_to_use or InventoryService.get_weighted_average_cost(db, tx.product_id, tx.warehouse_id),
                parent_transaction_id=tx.id,
                sales_order_id=tx.sales_order_id,
                sales_order_item_id=tx.sales_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه خروجی تکمیلی عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.utcnow()
            )
            db.add(adj_tx)
            if tx.sales_order_id:
                so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
                if so:
                    target_item = db.query(SalesOrderItem).get(tx.sales_order_item_id) if tx.sales_order_item_id else next((it for it in so.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.delivered_quantity += delta_q

        elif delta_q < 0:
            abs_delta = abs(delta_q)
            adj_tx = StockTransaction(
                transaction_type=TransactionType.IN,
                transaction_source=TransactionSource.OUT_ADJUSTMENT.value,
                product_id=tx.product_id,
                warehouse_id=tx.warehouse_id,
                quantity=abs_delta,
                secondary_quantity=abs(delta_sec) if delta_sec else None,
                secondary_uom=tx.secondary_uom,
                unit_price=tx.unit_price,
                parent_transaction_id=tx.id,
                sales_order_id=tx.sales_order_id,
                sales_order_item_id=tx.sales_order_item_id,
                fiscal_year_id=fy_id,
                reference_document=f"اصلاحیه بازگشت به انبار عطف به سند #{tx.id}",
                notes=adjustment_reason,
                status=DocumentStatus.APPROVED,
                created_by_id=current_user.id,
                approved_by_id=current_user.id,
                approved_at=datetime.utcnow()
            )
            db.add(adj_tx)
            if tx.sales_order_id:
                so = db.query(SalesOrder).filter(SalesOrder.id == tx.sales_order_id).first()
                if so:
                    target_item = db.query(SalesOrderItem).get(tx.sales_order_item_id) if tx.sales_order_item_id else next((it for it in so.items if it.product_id == tx.product_id), None)
                    if target_item:
                        target_item.delivered_quantity = max(0.0, target_item.delivered_quantity - abs_delta)

    # ۳. اصلاحیه صرفاً ریالی (اگر delta_q == 0 ولی قیمت تغییر کرده باشد)
    if delta_q == 0 and new_unit_price is not None and new_unit_price > 0 and new_unit_price != tx.unit_price:
        adj_tx = StockTransaction(
            transaction_type=tx.transaction_type,
            transaction_source=TransactionSource.PRICE_ADJUSTMENT.value,
            product_id=tx.product_id,
            warehouse_id=tx.warehouse_id,
            quantity=0.0,
            unit_price=new_unit_price,
            parent_transaction_id=tx.id,
            fiscal_year_id=fy_id,
            reference_document=f"اصلاحیه ریالی و بهای تمام‌شده سند #{tx.id}",
            notes=f"تغییر نرخ از {tx.unit_price} به {new_unit_price}. علت: {adjustment_reason}",
            status=DocumentStatus.APPROVED,
            created_by_id=current_user.id,
            approved_by_id=current_user.id,
            approved_at=datetime.utcnow()
        )
        db.add(adj_tx)
        tx.unit_price = new_unit_price

    db.commit()
    return RedirectResponse(url=f"/inventory/transactions?msg=" + quote(f"سند اصلاحیه برای تراکنش #{tx.id} با موفقیت صادر و اعمال شد"), status_code=303)
```

---

### ۴.۵. توابع محاسبه موجودی فیزیکی، آزاد و میانگین موزون (`src/services/inventory_service.py`)

```python
@staticmethod
def get_current_stock(db: Session, product_id: int, warehouse_id: int) -> float:
    """دریافت موجودی لحظه‌ای یک کالای خاص در یک انبار مشخص (فقط اسناد تایید شده)"""
    is_approved = or_(
        StockTransaction.status == DocumentStatus.APPROVED,
        StockTransaction.status == None
    )

    total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0)).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.warehouse_id == warehouse_id,
        StockTransaction.transaction_type == TransactionType.IN,
        is_approved
    ).scalar()

    total_out = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0)).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.warehouse_id == warehouse_id,
        StockTransaction.transaction_type == TransactionType.OUT,
        is_approved
    ).scalar()

    return float(total_in - total_out)


@staticmethod
def get_available_stock(db: Session, product_id: int, warehouse_id: int) -> float:
    """
    موجودی آزاد و قابل تخصیص کالا در انبار:
    ورودی‌های تاییدشده منهای (خروجی‌های تاییدشده + خروجی‌های رزروشده در انتظار تایید کارتابل)
    """
    is_approved = or_(
        StockTransaction.status == DocumentStatus.APPROVED,
        StockTransaction.status == None
    )

    total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.warehouse_id == warehouse_id,
        StockTransaction.transaction_type == TransactionType.IN,
        is_approved
    ).scalar() or 0.0

    # خروجی‌های قطعی + خروجی‌های رزروشده در انتظار تأیید
    out_condition = or_(
        is_approved,
        and_(
            StockTransaction.status == DocumentStatus.PENDING_APPROVAL,
            StockTransaction.transaction_type == TransactionType.OUT
        )
    )

    total_out = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
        StockTransaction.product_id == product_id,
        StockTransaction.warehouse_id == warehouse_id,
        StockTransaction.transaction_type == TransactionType.OUT,
        out_condition
    ).scalar() or 0.0

    return max(0.0, float(total_in - total_out))


@staticmethod
def get_weighted_average_cost(db: Session, product_id: int, warehouse_id: int = None) -> float:
    """
    محاسبه آخرین فی میانگین موزون متحرک (Moving Weighted Average Cost) کالا:
    مورد استفاده در نرخ‌گذاری خودکار حواله‌های خروج، انتقال بین انبارها و اصلاحات پایان سال.
    """
    query = (
        db.query(StockTransaction)
        .filter(
            StockTransaction.product_id == product_id,
            or_(
                StockTransaction.status == DocumentStatus.APPROVED,
                StockTransaction.status == None
            )
        )
        .order_by(StockTransaction.created_at.asc())
    )
    if warehouse_id:
        query = query.filter(StockTransaction.warehouse_id == warehouse_id)

    txs = query.all()
    balance_qty = 0.0
    balance_total = 0.0
    avg_rate = 0.0

    for tx in txs:
        qty = tx.quantity or 0.0
        price = tx.unit_price or 0.0
        if tx.transaction_type == TransactionType.IN:
            balance_qty += qty
            balance_total += (qty * price)
            avg_rate = (balance_total / balance_qty) if balance_qty > 0 else 0.0
        else:
            balance_qty = max(0.0, balance_qty - qty)
            balance_total = balance_qty * avg_rate

    return round(avg_rate, 4)
```

---

### ۴.۶. تجدید توزین دوم باسکول و حذف ثبت دوبل (`src/api/weighbridge_ui.py`)

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
            ticket.tare_weight = second_weight
        else:
            ticket.gross_weight = second_weight

        ticket.net_weight = abs(ticket.gross_weight - ticket.tare_weight)
        ticket.status = WeighbridgeStatus.COMPLETED
        ticket.completed_at = datetime.now()

        # محاسبه وزن متناسب با واحد کالا (تن یا کیلوگرم)
        is_ton = ticket.product and ticket.product.uom in ("تن", "Ton", "ton")
        net_qty = (ticket.net_weight / 1000.0) if is_ton else ticket.net_weight

        # بررسی وجود سند در انتظار تأیید در کارتابل انبار برای سفارش مرتبط
        pending_tx = None
        if ticket.purchase_order_id:
            pending_tx = db.query(StockTransaction).filter(
                StockTransaction.purchase_order_id == ticket.purchase_order_id,
                StockTransaction.product_id == ticket.product_id,
                StockTransaction.status == DocumentStatus.PENDING_APPROVAL
            ).first()
        elif ticket.sales_order_id:
            pending_tx = db.query(StockTransaction).filter(
                StockTransaction.sales_order_id == ticket.sales_order_id,
                StockTransaction.product_id == ticket.product_id,
                StockTransaction.status == DocumentStatus.PENDING_APPROVAL
            ).first()

        if pending_tx:
            # سند تکراری نساز! همان سند کارتابل را با وزن باسکول به‌روزرسانی کن
            pending_tx.quantity = round(net_qty, 3)
            pending_tx.weighbridge_ticket_id = ticket.id
            pending_tx.reference_document = f"{pending_tx.reference_document or ''} | قبض باسکول {ticket.ticket_number}".strip(" |")
            ticket.stock_transaction_id = pending_tx.id
        else:
            # ایجاد یک سند در انتظار تأیید (PENDING_APPROVAL) در کارتابل انبار
            tx_type = TransactionType.IN if (ticket.supplier_id or ticket.purchase_order_id) else TransactionType.OUT
            tx_src = TransactionSource.PURCHASE.value if tx_type == TransactionType.IN else TransactionSource.SALES.value
            tx = StockTransaction(
                transaction_type=tx_type,
                transaction_source=tx_src,
                product_id=ticket.product_id,
                warehouse_id=ticket.warehouse_id,
                quantity=round(net_qty, 3),
                supplier_id=ticket.supplier_id,
                customer_id=ticket.customer_id,
                purchase_order_id=ticket.purchase_order_id,
                sales_order_id=ticket.sales_order_id,
                weighbridge_ticket_id=ticket.id,
                reference_document=f"قبض باسکول {ticket.ticket_number}",
                status=DocumentStatus.PENDING_APPROVAL,
                created_by_id=current_user.id
            )
            db.add(tx)
            db.flush()
            ticket.stock_transaction_id = tx.id

        db.commit()
        return RedirectResponse(
            url=f"/weighbridge/{ticket.id}?msg=" + quote("توزین دوم انجام و با کارتابل انبار یکپارچه گردید"),
            status_code=303
        )
    except Exception as e:
        db.rollback()
        raise
```

---

### ۴.۷. عملیات بستن سال مالی و افتتاح دوره جدید (`src/api/inventory_ui.py`)

```python
@router.post("/fiscal-year-close")
async def close_fiscal_year(
    request: Request,
    new_year_name: str = Form(...),
    new_year_start_date: str = Form(...),
    new_year_end_date: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """عملیات رسمی پایان دوره مالی و انتقال مانده‌های مثبت به سال جدید"""
    active_year = db.query(FiscalYear).filter(FiscalYear.is_active == True, FiscalYear.is_closed == False).first()
    if not active_year:
        raise HTTPException(status_code=400, detail="هیچ سال مالی فعالی جهت بستن یافت نشد.")

    # ۱. بررسی سلامت اسناد پیش از بستن سال
    pending_txs_count = db.query(StockTransaction).filter(
        StockTransaction.status == DocumentStatus.PENDING_APPROVAL
    ).count()
    if pending_txs_count > 0:
        raise HTTPException(status_code=400, detail=f"تعداد {pending_txs_count} سند معلق در کارتابل انبار وجود دارد. تا تعیین تکلیف این اسناد امکان بستن سال مالی وجود ندارد.")

    open_tickets_count = db.query(WeighbridgeTicket).filter(
        WeighbridgeTicket.status == WeighbridgeStatus.FIRST_WEIGHING
    ).count()
    if open_tickets_count > 0:
        raise HTTPException(status_code=400, detail=f"تعداد {open_tickets_count} قبض باسکول نیمه‌کاره در فاز اول توزین وجود دارد.")

    # ۲. بستن سال مالی فعلی
    active_year.is_active = False
    active_year.is_closed = True
    active_year.closed_at = datetime.utcnow()
    active_year.closed_by_id = current_user.id

    # ۳. ایجاد سال مالی جدید
    new_fy = FiscalYear(
        name=new_year_name.strip(),
        start_date=new_year_start_date.strip(),
        end_date=new_year_end_date.strip(),
        is_active=True,
        is_closed=False
    )
    db.add(new_fy)
    db.flush()

    # ۴. انتقال مانده‌های پایان دوره به عنوان سند موجودی ابتدای دوره (OPENING_BALANCE)
    products = db.query(Product).filter(Product.is_active == True).all()
    warehouses = db.query(Warehouse).all()
    transferred_count = 0

    for w in warehouses:
        for p in products:
            qty = InventoryService.get_current_stock(db, p.id, w.id)
            # حذف کالاهای با موجودی صفر (فقط موجودی‌های مثبت منتقل می‌شوند)
            if qty > 0.0001:
                sec_qty = InventoryService.get_current_secondary_stock(db, p.id, w.id)
                avg_cost = InventoryService.get_weighted_average_cost(db, p.id, w.id)
                op_tx = StockTransaction(
                    transaction_type=TransactionType.IN,
                    transaction_source=TransactionSource.OPENING_BALANCE.value,
                    product_id=p.id,
                    warehouse_id=w.id,
                    quantity=round(qty, 3),
                    secondary_quantity=round(sec_qty, 3) if sec_qty else None,
                    secondary_uom=p.secondary_uom,
                    unit_price=round(avg_cost, 2),
                    status=DocumentStatus.APPROVED,
                    reference_document=f"موجودی اول دوره سال {new_fy.name} (انتقالی از {active_year.name})",
                    notes="سند افتتاحیه سیستمی پایان سال مالی",
                    fiscal_year_id=new_fy.id,
                    created_by_id=current_user.id,
                    approved_by_id=current_user.id,
                    approved_at=datetime.utcnow()
                )
                db.add(op_tx)
                transferred_count += 1

    db.commit()
    return RedirectResponse(
        url="/inventory/fiscal-years?msg=" + quote(f"سال مالی {active_year.name} بسته شد و سال {new_fy.name} با {transferred_count} قلم سند افتتاحیه با موفقیت فعال گردید"),
        status_code=303
    )
```
