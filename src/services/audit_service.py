from typing import Optional
from sqlalchemy.orm import Session
from src.domain_model.inventory_models import AuditLog

class AuditService:
    @staticmethod
    def log(
        db: Session,
        action: str,
        entity_name: str,
        entity_id: Optional[str] = None,
        user_id: Optional[int] = None,
        user_name: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """ثبت رویداد حسابرسی در پایگاه‌داده"""
        try:
            log_entry = AuditLog(
                user_id=user_id,
                user_name=user_name or "سیستم",
                action=action,
                entity_name=entity_name,
                entity_id=str(entity_id) if entity_id else None,
                details=details,
                ip_address=ip_address
            )
            db.add(log_entry)
            db.commit()
            return log_entry
        except Exception as e:
            db.rollback()
            print(f"Audit log warning: {e}")
            return None
