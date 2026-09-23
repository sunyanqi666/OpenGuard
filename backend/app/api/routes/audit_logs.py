import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from sqlmodel import col, func, select

from app.api.deps import CurrentSecurityEditor, SessionDep
from app.models import (
    AuditAction,
    AuditLog,
    AuditLogPublic,
    AuditLogsPublic,
    User,
)

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("/", response_model=AuditLogsPublic)
def read_audit_logs(
    session: SessionDep,
    _current_user: CurrentSecurityEditor,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    action: AuditAction | None = None,
    resource_type: str | None = Query(default=None, max_length=64),
    actor_id: uuid.UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> Any:
    filters: list[Any] = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(col(AuditLog.resource_type).ilike(resource_type.strip()))
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)
    if created_from:
        filters.append(col(AuditLog.created_at) >= created_from)
    if created_to:
        filters.append(col(AuditLog.created_at) <= created_to)
    count = session.exec(
        select(func.count()).select_from(AuditLog).where(*filters)
    ).one()
    rows = session.exec(
        select(AuditLog, User)
        .join(User, col(AuditLog.actor_id) == col(User.id), isouter=True)
        .where(*filters)
        .order_by(col(AuditLog.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return AuditLogsPublic(
        data=[
            AuditLogPublic(
                **log.model_dump(exclude={"action"}),
                action=AuditAction(log.action),
                actor_email=user.email if user else None,
            )
            for log, user in rows
        ],
        count=count,
    )
