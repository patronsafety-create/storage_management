from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_
from datetime import datetime, timedelta

from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType, FiscalYear
from src.domain_model.enums import DocumentStatus


class InventoryService:
    """
    لایه سرویس برای مدیریت منطق تجاری انبار (Business Logic)
    با پشتیبانی از تفکیک سال مالی، گردش تأیید اسناد، موتور دو واحدی، و نرخ‌گذاری میانگین موزون.
    """

    @staticmethod
    def get_active_fiscal_year(db: Session) -> FiscalYear:
        """
        واکشی سال مالی فعال جاری (is_active=True, is_closed=False).
        در صورت عدم وجود، سال مالی پیش‌فرض ایجاد و تراکنش‌های فاقد سال مالی مایگریت می‌شوند.
        """
        active_fy = db.query(FiscalYear).filter(
            FiscalYear.is_active == True,
            FiscalYear.is_closed == False
        ).first()

        if not active_fy:
            active_fy = FiscalYear(
                name="سال مالی ۱۴۰۴",
                start_date="1404-01-01",
                end_date="1404-12-29",
                is_active=True,
                is_closed=False
            )
            db.add(active_fy)
            db.commit()
            db.refresh(active_fy)

        # مایگریشن خودکار: اتصال اسناد فاقد سال مالی به سال مالی فعال جاری
        orphaned = db.query(StockTransaction).filter(StockTransaction.fiscal_year_id == None).all()
        if orphaned:
            for tx in orphaned:
                tx.fiscal_year_id = active_fy.id
            db.commit()

        return active_fy
    
    @staticmethod
    def calculate_stock_balances(db: Session, fiscal_year_id: int = None) -> list[dict]:
        """
        محاسبه مانده لحظه‌ای مقداری و دو واحدی کالاها به تفکیک هر انبار در سال مالی فعال.
        جلوگیری قطعی از دو برابر شدن موجودی پس از انتقال به سال مالی جدید.
        """
        active_fy = db.query(FiscalYear).get(fiscal_year_id) if fiscal_year_id else InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None

        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

        fy_filter = (StockTransaction.fiscal_year_id == fy_id) if fy_id else True

        balance_query = (
            db.query(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Product.uom.label("uom"),
                Product.secondary_uom.label("secondary_uom"),
                Product.min_stock.label("min_stock"),
                Product.reorder_point.label("reorder_point"),
                Warehouse.id.label("warehouse_id"),
                Warehouse.name.label("warehouse_name"),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.IN, is_approved, fy_filter), StockTransaction.quantity), else_=0)), 0
                ).label('total_in'),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.OUT, is_approved, fy_filter), StockTransaction.quantity), else_=0)), 0
                ).label('total_out'),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.IN, is_approved, fy_filter), StockTransaction.secondary_quantity), else_=0)), 0
                ).label('sec_in'),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.OUT, is_approved, fy_filter), StockTransaction.secondary_quantity), else_=0)), 0
                ).label('sec_out')
            )
            .outerjoin(StockTransaction, Product.id == StockTransaction.product_id)
            .outerjoin(Warehouse, StockTransaction.warehouse_id == Warehouse.id)
            .group_by(Product.id, Product.name, Product.uom, Product.secondary_uom, Product.min_stock, Product.reorder_point, Warehouse.id, Warehouse.name)
            .all()
        )

        stock_balances = []
        for row in balance_query:
            current_balance = row.total_in - row.total_out
            sec_balance = row.sec_in - row.sec_out
            stock_balances.append({
                "product_id": row.product_id,
                "name": row.product_name,
                "uom": row.uom,
                "secondary_uom": row.secondary_uom,
                "secondary_balance": sec_balance if row.secondary_uom else None,
                "min_stock": row.min_stock or 0.0,
                "reorder_point": row.reorder_point or 0.0,
                "warehouse_id": row.warehouse_id,
                "warehouse": row.warehouse_name or "بدون گردش در انبار",
                "total_in": row.total_in,
                "total_out": row.total_out,
                "current_balance": current_balance
            })
            
        return stock_balances

    @staticmethod
    def get_current_stock(db: Session, product_id: int, warehouse_id: int, fiscal_year_id: int = None) -> float:
        """دریافت موجودی لحظه‌ای یک کالای خاص در یک انبار مشخص در سال مالی جاری (فقط اسناد تایید شده)"""
        active_fy = db.query(FiscalYear).get(fiscal_year_id) if fiscal_year_id else InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        fy_filter = (StockTransaction.fiscal_year_id == fy_id) if fy_id else True

        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

        total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.IN,
            is_approved,
            fy_filter
        ).scalar()

        total_out = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.OUT,
            is_approved,
            fy_filter
        ).scalar()

        return float(total_in - total_out)

    @staticmethod
    def get_total_stock_all_warehouses(db: Session, product_id: int, fiscal_year_id: int = None) -> float:
        """مجموع موجودی در دسترس یک کالا در تمامی انبارها در سال مالی جاری (فقط اسناد تایید شده)"""
        active_fy = db.query(FiscalYear).get(fiscal_year_id) if fiscal_year_id else InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        fy_filter = (StockTransaction.fiscal_year_id == fy_id) if fy_id else True

        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

        total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.transaction_type == TransactionType.IN,
            is_approved,
            fy_filter
        ).scalar() or 0.0

        total_out = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.transaction_type == TransactionType.OUT,
            is_approved,
            fy_filter
        ).scalar() or 0.0

        return float(total_in - total_out)

    @staticmethod
    def get_available_stock(db: Session, product_id: int, warehouse_id: int, fiscal_year_id: int = None) -> float:
        """
        موجودی آزاد و قابل تخصیص کالا در انبار در سال مالی جاری:
        ورودی‌های تاییدشده منهای (خروجی‌های تاییدشده + خروجی‌های رزروشده در انتظار تایید کارتابل)
        """
        active_fy = db.query(FiscalYear).get(fiscal_year_id) if fiscal_year_id else InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        fy_filter = (StockTransaction.fiscal_year_id == fy_id) if fy_id else True

        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

        total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.IN,
            is_approved,
            fy_filter
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
            out_condition,
            fy_filter
        ).scalar() or 0.0

        return max(0.0, float(total_in - total_out))

    @staticmethod
    def get_current_secondary_stock(db: Session, product_id: int, warehouse_id: int, fiscal_year_id: int = None) -> float:
        """مانده موجودی واحد فرعی (تعداد شاخه/بندیل/کیسه) در انبار در سال مالی جاری"""
        active_fy = db.query(FiscalYear).get(fiscal_year_id) if fiscal_year_id else InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        fy_filter = (StockTransaction.fiscal_year_id == fy_id) if fy_id else True

        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

        sec_in = db.query(func.coalesce(func.sum(StockTransaction.secondary_quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.IN,
            is_approved,
            fy_filter
        ).scalar() or 0.0

        sec_out = db.query(func.coalesce(func.sum(StockTransaction.secondary_quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.OUT,
            is_approved,
            fy_filter
        ).scalar() or 0.0

        return float(sec_in - sec_out)

    @staticmethod
    def get_weighted_average_cost(db: Session, product_id: int, warehouse_id: int = None, fiscal_year_id: int = None, target_currency: str = None) -> float:
        """
        محاسبه آخرین فی میانگین موزون متحرک (Moving Weighted Average Cost) کالا در سال مالی جاری
        با جلوگیری از قاطی شدن ارزهای ریال (IRR) و لیر (TRY) از طریق تبدیل نرخ ارز (exchange_rate)
        یا انزوای کاردکس بر مبنای ارز پایه انبار/ارز هدف:
        مورد استفاده در نرخ‌گذاری خودکار حواله‌های خروج، انتقال بین انبارها و اصلاحات پایان سال.
        مرتب‌سازی توالی رویدادها بر اساس transaction_date و سپس id.
        """
        active_fy = db.query(FiscalYear).get(fiscal_year_id) if fiscal_year_id else InventoryService.get_active_fiscal_year(db)
        fy_id = active_fy.id if active_fy else None
        fy_filter = (StockTransaction.fiscal_year_id == fy_id) if fy_id else True

        target_wh = db.query(Warehouse).get(warehouse_id) if warehouse_id else None
        base_currency = target_currency or (target_wh.currency if (target_wh and target_wh.currency) else "IRR")

        query = (
            db.query(StockTransaction)
            .filter(
                StockTransaction.product_id == product_id,
                or_(
                    StockTransaction.status == DocumentStatus.APPROVED,
                    StockTransaction.status == None
                ),
                fy_filter
            )
            .order_by(StockTransaction.transaction_date.asc(), StockTransaction.id.asc())
        )
        if warehouse_id:
            query = query.filter(StockTransaction.warehouse_id == warehouse_id)

        txs = query.all()
        balance_qty = 0.0
        balance_total = 0.0
        avg_rate = 0.0

        # شناسایی آخرین ضریب برابری ارز در تراکنش‌ها
        latest_ex_rate = None
        for tx in txs:
            r = getattr(tx, "exchange_rate", 1.0) or 1.0
            if r > 1.0:
                latest_ex_rate = r

        for tx in txs:
            qty = tx.quantity or 0.0
            raw_price = tx.unit_price or 0.0
            tx_curr = getattr(tx, "currency", None) or "IRR"
            ex_rate = getattr(tx, "exchange_rate", 1.0) or 1.0

            # اگر ارز تراکنش با ارز پایه انبار/ارز هدف مغایرت داشته باشد، نرخ با ضریب تبدیل اعمال می‌شود
            if tx_curr == base_currency:
                price = raw_price
            elif tx_curr == "TRY" and base_currency == "IRR":
                rate = ex_rate if ex_rate > 1.0 else (latest_ex_rate or 1.0)
                price = raw_price * rate
            elif tx_curr == "IRR" and base_currency == "TRY":
                rate = ex_rate if ex_rate > 1.0 else (latest_ex_rate or 16000.0)
                price = (raw_price / rate) if rate > 0 else raw_price
            elif ex_rate > 0:
                price = raw_price * ex_rate
            else:
                price = raw_price

            if tx.transaction_type == TransactionType.IN:
                balance_qty += qty
                balance_total += (qty * price)
                avg_rate = (balance_total / balance_qty) if balance_qty > 0 else 0.0
            else:
                balance_qty = max(0.0, balance_qty - qty)
                balance_total = balance_qty * avg_rate

        return round(avg_rate, 4)