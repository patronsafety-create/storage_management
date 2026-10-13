from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_
from datetime import datetime, timedelta

from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType
from src.domain_model.enums import DocumentStatus


class InventoryService:
    """
    لایه سرویس برای مدیریت منطق تجاری انبار (Business Logic)
    با پشتیبانی از گردش تأیید اسناد، موتور دو واحدی و کنترل هشدارهای موجودی.
    """
    
    @staticmethod
    def calculate_stock_balances(db: Session) -> list[dict]:
        """محاسبه مانده لحظه‌ای مقداری و دو واحدی کالاها به تفکیک هر انبار (صرفاً اسناد تایید شده)"""
        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

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
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.IN, is_approved), StockTransaction.quantity), else_=0)), 0
                ).label('total_in'),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.OUT, is_approved), StockTransaction.quantity), else_=0)), 0
                ).label('total_out'),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.IN, is_approved), StockTransaction.secondary_quantity), else_=0)), 0
                ).label('sec_in'),
                func.coalesce(
                    func.sum(case((and_(StockTransaction.transaction_type == TransactionType.OUT, is_approved), StockTransaction.secondary_quantity), else_=0)), 0
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
    def get_total_stock_all_warehouses(db: Session, product_id: int) -> float:
        """مجموع موجودی در دسترس یک کالا در تمامی انبارها (فقط اسناد تایید شده)"""
        is_approved = or_(
            StockTransaction.status == DocumentStatus.APPROVED,
            StockTransaction.status == None
        )

        total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.transaction_type == TransactionType.IN,
            is_approved
        ).scalar() or 0.0

        total_out = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0.0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.transaction_type == TransactionType.OUT,
            is_approved
        ).scalar() or 0.0

        return float(total_in - total_out)