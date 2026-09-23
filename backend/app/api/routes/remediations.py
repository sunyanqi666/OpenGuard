import uuid
from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import and_, case, or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentSecurityEditor, CurrentUser, SessionDep
from app.models import (
    AuditAction,
    AuditLog,
    Component,
    Message,
    Remediation,
    RemediationCreate,
    RemediationPublic,
    RemediationsPublic,
    RemediationStatus,
    RemediationSummary,
    RemediationUpdate,
    Severity,
    User,
    Vulnerability,
    VulnerabilityComponent,
    get_datetime_utc,
)

router = APIRouter(prefix="/remediations", tags=["remediations"])


@router.get("/", response_model=RemediationsPublic)
def read_remediations(
    session: SessionDep,
    current_user: CurrentUser,
    vulnerability_id: uuid.UUID | None = None,
    component_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=255),
    remediation_status: RemediationStatus | None = Query(default=None, alias="status"),
    severity: Severity | None = None,
    assignee_id: uuid.UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    overdue_only: bool = False,
    due_soon_only: bool = False,
    my_only: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> Any:
    filters: list[Any] = []
    if vulnerability_id:
        filters.append(Remediation.vulnerability_id == vulnerability_id)
    if component_id:
        filters.append(Remediation.component_id == component_id)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                col(Vulnerability.cve_id).ilike(pattern),
                col(Vulnerability.title).ilike(pattern),
                col(Component.name).ilike(pattern),
                col(Component.purl).ilike(pattern),
            )
        )
    if remediation_status:
        filters.append(Remediation.status == remediation_status)
    if severity:
        filters.append(Vulnerability.severity == severity)
    if assignee_id:
        filters.append(Remediation.assignee_id == assignee_id)
    if my_only:
        filters.append(Remediation.assignee_id == current_user.id)
    if due_from:
        filters.append(col(Remediation.due_date) >= due_from)
    if due_to:
        filters.append(col(Remediation.due_date) <= due_to)
    today = get_datetime_utc().date()
    unfinished = col(Remediation.status).not_in(
        [RemediationStatus.FIXED, RemediationStatus.IGNORED]
    )
    if overdue_only:
        filters.extend([unfinished, col(Remediation.due_date) < today])
    if due_soon_only:
        filters.extend(
            [
                unfinished,
                col(Remediation.due_date) >= today,
                col(Remediation.due_date) <= today + timedelta(days=3),
            ]
        )
    base = (
        select(Remediation, Vulnerability, Component, User)
        .join(Vulnerability)
        .join(
            Component, col(Remediation.component_id) == col(Component.id), isouter=True
        )
        .join(User, col(Remediation.assignee_id) == col(User.id), isouter=True)
        .where(*filters)
    )
    count = session.exec(
        select(func.count())
        .select_from(Remediation)
        .join(Vulnerability)
        .join(
            Component, col(Remediation.component_id) == col(Component.id), isouter=True
        )
        .where(*filters)
    ).one()
    statement = (
        base.order_by(
            case(
                (and_(unfinished, col(Remediation.due_date) < today), 0),
                (
                    and_(
                        unfinished,
                        col(Remediation.due_date) <= today + timedelta(days=3),
                    ),
                    1,
                ),
                else_=2,
            ),
            col(Remediation.due_date).asc().nulls_last(),
            col(Remediation.updated_at).desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    return RemediationsPublic(
        data=[_public(*row) for row in session.exec(statement).all()], count=count
    )


@router.get("/summary", response_model=RemediationSummary)
def read_remediation_summary(
    session: SessionDep,
    current_user: CurrentUser,
    my_only: bool = False,
) -> RemediationSummary:
    statement = select(Remediation)
    if my_only:
        statement = statement.where(Remediation.assignee_id == current_user.id)
    records = session.exec(statement).all()
    today = get_datetime_utc().date()
    month_start = today.replace(day=1)
    unfinished = {
        RemediationStatus.PENDING.value,
        RemediationStatus.IN_PROGRESS.value,
    }
    status_values = [str(item.status) for item in records]
    fixed = status_values.count(RemediationStatus.FIXED.value)
    ignored = status_values.count(RemediationStatus.IGNORED.value)
    completed = fixed + ignored
    return RemediationSummary(
        total=len(records),
        pending=status_values.count(RemediationStatus.PENDING.value),
        in_progress=status_values.count(RemediationStatus.IN_PROGRESS.value),
        fixed=fixed,
        ignored=ignored,
        overdue=sum(
            item.status in unfinished
            and item.due_date is not None
            and item.due_date < today
            for item in records
        ),
        due_soon=sum(
            item.status in unfinished
            and item.due_date is not None
            and today <= item.due_date <= today + timedelta(days=3)
            for item in records
        ),
        completed_this_month=sum(
            item.status == RemediationStatus.FIXED
            and item.updated_at.date() >= month_start
            for item in records
        ),
        completion_rate=round(completed / len(records) * 100, 1) if records else 0,
    )


@router.post("/", response_model=RemediationPublic, status_code=status.HTTP_201_CREATED)
def create_remediation(
    *,
    session: SessionDep,
    current_user: CurrentSecurityEditor,
    remediation_in: RemediationCreate,
) -> Any:
    vulnerability = session.get(Vulnerability, remediation_in.vulnerability_id)
    component = session.get(Component, remediation_in.component_id)
    if vulnerability is None or component is None:
        raise HTTPException(
            status_code=404, detail="Vulnerability or component not found"
        )
    linked = session.exec(
        select(VulnerabilityComponent).where(
            VulnerabilityComponent.vulnerability_id == vulnerability.id,
            VulnerabilityComponent.component_id == component.id,
        )
    ).first()
    if linked is None:
        raise HTTPException(
            status_code=422, detail="Create the association before remediation"
        )
    if (
        remediation_in.assignee_id
        and session.get(User, remediation_in.assignee_id) is None
    ):
        raise HTTPException(status_code=404, detail="Assignee not found")
    remediation = Remediation.model_validate(remediation_in)
    session.add(remediation)
    session.add(
        _audit(
            current_user.id,
            AuditAction.CREATE,
            remediation,
            {},
            remediation_in.model_dump(mode="json"),
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="Remediation already exists")
    session.refresh(remediation)
    assignee = (
        session.get(User, remediation.assignee_id) if remediation.assignee_id else None
    )
    return _public(remediation, vulnerability, component, assignee)


@router.patch("/{remediation_id}", response_model=RemediationPublic)
def update_remediation(
    *,
    session: SessionDep,
    current_user: CurrentSecurityEditor,
    remediation_id: uuid.UUID,
    remediation_in: RemediationUpdate,
) -> Any:
    remediation = session.get(Remediation, remediation_id)
    if remediation is None:
        raise HTTPException(status_code=404, detail="Remediation not found")
    data = remediation_in.model_dump(exclude_unset=True)
    if data.get("assignee_id") and session.get(User, data["assignee_id"]) is None:
        raise HTTPException(status_code=404, detail="Assignee not found")
    before = {
        key: getattr(remediation, key)
        for key in data
        if getattr(remediation, key) != data[key]
    }
    if before:
        old_status = remediation.status
        remediation.sqlmodel_update(data)
        remediation.updated_at = get_datetime_utc()
        action = (
            AuditAction.STATUS_CHANGE
            if remediation.status != old_status
            else AuditAction.UPDATE
        )
        session.add(remediation)
        session.add(
            _audit(
                current_user.id,
                action,
                remediation,
                before,
                {key: getattr(remediation, key) for key in before},
            )
        )
        session.commit()
        session.refresh(remediation)
    vulnerability = session.get(Vulnerability, remediation.vulnerability_id)
    component = (
        session.get(Component, remediation.component_id)
        if remediation.component_id
        else None
    )
    assignee = (
        session.get(User, remediation.assignee_id) if remediation.assignee_id else None
    )
    if vulnerability is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return _public(remediation, vulnerability, component, assignee)


@router.delete("/{remediation_id}")
def delete_remediation(
    session: SessionDep,
    current_user: CurrentSecurityEditor,
    remediation_id: uuid.UUID,
) -> Message:
    remediation = session.get(Remediation, remediation_id)
    if remediation is None:
        raise HTTPException(status_code=404, detail="Remediation not found")
    session.add(
        _audit(
            current_user.id,
            AuditAction.DELETE,
            remediation,
            {
                **remediation.model_dump(mode="json", exclude={"status"}),
                "status": str(remediation.status),
            },
            {},
        )
    )
    session.delete(remediation)
    session.commit()
    return Message(message="Remediation deleted successfully")


def _public(
    remediation: Remediation,
    vulnerability: Vulnerability,
    component: Component | None,
    assignee: User | None,
) -> RemediationPublic:
    return RemediationPublic(
        **remediation.model_dump(exclude={"status"}),
        status=RemediationStatus(remediation.status),
        cve_id=vulnerability.cve_id,
        component_name=component.name if component else None,
        component_purl=component.purl if component else None,
        vulnerability_severity=vulnerability.severity,
        assignee_name=(assignee.full_name or assignee.email) if assignee else None,
    )


def _audit(
    actor_id: uuid.UUID,
    action: AuditAction,
    remediation: Remediation,
    before: dict[str, Any],
    after: dict[str, Any],
) -> AuditLog:
    def jsonable(values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in values.items()
        }

    return AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type="remediation",
        resource_id=remediation.id,
        summary=f"Updated remediation for {remediation.vulnerability_id}",
        changes={"before": jsonable(before), "after": jsonable(after)},
    )
