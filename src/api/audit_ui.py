from typing import Optional
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.infrastructure.database import get_db
from src.api.auth import get_current_user
from src.domain_model.auth_models import User
from src.domain_model.inventory_models import AuditLog

router = APIRouter(prefix="/admin/audit-logs", tags=["Audit Logs"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def list_audit_logs(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    action_filter: Optional[str] = Query(None),
    entity_filter: Optional[str] = Query(None)
):
    """مشاهده لاگ جامع حسابرسی رویدادهای سیستم و ردپای امنیتی"""
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())

    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if entity_filter:
        query = query.filter(AuditLog.entity_name == entity_filter)

    logs = query.limit(200).all()

    return templates.TemplateResponse(
        request=request,
        name="audit_logs.html",
        context={
            "request": request,
            "logs": logs,
            "action_filter": action_filter,
            "entity_filter": entity_filter,
            "user": current_user
        }
    )
