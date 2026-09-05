from sqlalchemy.orm import Session
from sqlalchemy import func, case

from src.domain_model.inventory_models import Product, StockTransaction, TransactionType

class InventoryService:
    """
    لایه سرویس برای مدیریت منطق تجاری انبار (Business Logic). 
    این کلاس کاملاً از محیط وب (FastAPI) و فرم‌های HTML ایزوله است.
    """
    
    @staticmethod
    def calculate_stock_balances(db: Session) -> list[dict]:
        """
        محاسبه مانده لحظه‌ای انبار بر اساس تجمیع رسیدها (IN) و کسر حواله‌ها (OUT)
        """
        balance_query = (
            db.query(
                Product.name.label("product_name"),
                Product.uom.label("uom"),
                func.coalesce(
                    func.sum(case((StockTransaction.transaction_type == TransactionType.IN, StockTransaction.quantity), else_=0)), 0
                ).label('total_in'),
                func.coalesce(
                    func.sum(case((StockTransaction.transaction_type == TransactionType.OUT, StockTransaction.quantity), else_=0)), 0
                ).label('total_out')
            )
            .outerjoin(StockTransaction, Product.id == StockTransaction.product_id)
            .group_by(Product.id, Product.name, Product.uom)
            .all()
        )

        stock_balances = []
        for row in balance_query:
            stock_balances.append({
                "name": row.product_name,
                "uom": row.uom,
                "total_in": row.total_in,
                "total_out": row.total_out,
                "current_balance": row.total_in - row.total_out
            })
            
        return stock_balances