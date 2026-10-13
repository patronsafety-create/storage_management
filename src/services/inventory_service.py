from sqlalchemy.orm import Session
from sqlalchemy import func, case

from src.domain_model.inventory_models import Product, Warehouse, StockTransaction, TransactionType

class InventoryService:
    """
    لایه سرویس برای مدیریت منطق تجاری انبار (Business Logic).
    """
    
    @staticmethod
    def calculate_stock_balances(db: Session) -> list[dict]:
        """محاسبه مانده لحظه‌ای کالاها به تفکیک هر انبار"""
        balance_query = (
            db.query(
                Product.id.label("product_id"),
                Product.name.label("product_name"),
                Product.uom.label("uom"),
                Warehouse.id.label("warehouse_id"),
                Warehouse.name.label("warehouse_name"),
                func.coalesce(
                    func.sum(case((StockTransaction.transaction_type == TransactionType.IN, StockTransaction.quantity), else_=0)), 0
                ).label('total_in'),
                func.coalesce(
                    func.sum(case((StockTransaction.transaction_type == TransactionType.OUT, StockTransaction.quantity), else_=0)), 0
                ).label('total_out')
            )
            .outerjoin(StockTransaction, Product.id == StockTransaction.product_id)
            .outerjoin(Warehouse, StockTransaction.warehouse_id == Warehouse.id)
            .group_by(Product.id, Product.name, Product.uom, Warehouse.id, Warehouse.name)
            .all()
        )

        stock_balances = []
        for row in balance_query:
            stock_balances.append({
                "product_id": row.product_id,
                "name": row.product_name,
                "uom": row.uom,
                "warehouse_id": row.warehouse_id,
                "warehouse": row.warehouse_name or "بدون گردش در انبار",
                "total_in": row.total_in,
                "total_out": row.total_out,
                "current_balance": row.total_in - row.total_out
            })
            
        return stock_balances

    @staticmethod
    def get_current_stock(db: Session, product_id: int, warehouse_id: int) -> float:
        """دریافت موجودی لحظه‌ای یک کالای خاص در یک انبار مشخص"""
        total_in = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.IN
        ).scalar()

        total_out = db.query(func.coalesce(func.sum(StockTransaction.quantity), 0)).filter(
            StockTransaction.product_id == product_id,
            StockTransaction.warehouse_id == warehouse_id,
            StockTransaction.transaction_type == TransactionType.OUT
        ).scalar()

        return total_in - total_out