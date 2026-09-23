import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentSuperuser, CurrentUser, SessionDep
from app.models import (
    AuditAction,
    AuditLog,
    Message,
    Severity,
    VulnerabilitiesPublic,
    Vulnerability,
    VulnerabilityCreate,
    VulnerabilityPublic,
    VulnerabilityUpdate,
    get_datetime_utc,
)

router = APIRouter(prefix="/vulnerabilities", tags=["vulnerabilities"])


@router.post(
    "/", response_model=VulnerabilityPublic, status_code=status.HTTP_201_CREATED
)
def create_vulnerability(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    vulnerability_in: VulnerabilityCreate,
) -> Any:
    """Create a CVE manually as an optional administrator workflow."""
    if session.exec(
        select(Vulnerability).where(Vulnerability.cve_id == vulnerability_in.cve_id)
    ).first():
        raise _cve_id_conflict()

    vulnerability = Vulnerability.model_validate(vulnerability_in)
    session.add(vulnerability)
    session.add(
        AuditLog(
            actor_id=current_user.id,
            action=AuditAction.CREATE,
            resource_type="vulnerability",
            resource_id=vulnerability.id,
            summary=f"Created {vulnerability.cve_id}",
            changes={"after": vulnerability_in.model_dump(mode="json")},
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _cve_id_conflict()
    session.refresh(vulnerability)
    return vulnerability


@router.get("/", response_model=VulnerabilitiesPublic)
def read_vulnerabilities(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=255),
    severity: Severity | None = None,
    source_name: str | None = Query(default=None, max_length=32),
    min_cvss: Decimal | None = Query(default=None, ge=0, le=10),
    max_cvss: Decimal | None = Query(default=None, ge=0, le=10),
    published_from: datetime | None = None,
    published_to: datetime | None = None,
) -> Any:
    """Return an authenticated, filtered and paginated CVE list."""
    if min_cvss is not None and max_cvss is not None and min_cvss > max_cvss:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="min_cvss must not be greater than max_cvss",
        )
    if published_from and published_to and published_from > published_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="published_from must not be later than published_to",
        )

    filters: list[Any] = []
    normalized_search = search.strip() if search else None
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                col(Vulnerability.cve_id).ilike(pattern),
                col(Vulnerability.title).ilike(pattern),
                col(Vulnerability.description).ilike(pattern),
            )
        )
    if severity is not None:
        filters.append(Vulnerability.severity == severity)
    if source_name:
        filters.append(col(Vulnerability.source_name).ilike(source_name.strip()))

    effective_cvss = func.coalesce(
        Vulnerability.cvss_score_v4,
        Vulnerability.cvss_score_v3,
        Vulnerability.cvss_score_v2,
    )
    if min_cvss is not None:
        filters.append(effective_cvss >= min_cvss)
    if max_cvss is not None:
        filters.append(effective_cvss <= max_cvss)
    if published_from is not None:
        filters.append(col(Vulnerability.source_publish_date) >= published_from)
    if published_to is not None:
        filters.append(col(Vulnerability.source_publish_date) <= published_to)

    count_statement = select(func.count()).select_from(Vulnerability).where(*filters)
    count = session.exec(count_statement).one()
    statement = (
        select(Vulnerability)
        .where(*filters)
        .order_by(
            col(Vulnerability.source_publish_date).desc().nulls_last(),
            col(Vulnerability.cve_id).desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    vulnerabilities = session.exec(statement).all()
    return VulnerabilitiesPublic(
        data=[VulnerabilityPublic.model_validate(item) for item in vulnerabilities],
        count=count,
    )


@router.get("/{vulnerability_id}", response_model=VulnerabilityPublic)
def read_vulnerability(
    session: SessionDep,
    _current_user: CurrentUser,
    vulnerability_id: uuid.UUID,
) -> Any:
    vulnerability = session.get(Vulnerability, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return vulnerability


@router.patch("/{vulnerability_id}", response_model=VulnerabilityPublic)
def update_vulnerability(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    vulnerability_id: uuid.UUID,
    vulnerability_in: VulnerabilityUpdate,
) -> Any:
    vulnerability = session.get(Vulnerability, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    update_data = vulnerability_in.model_dump(exclude_unset=True)
    if update_data.get("severity") is None and "severity" in update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="severity cannot be null",
        )

    before = {
        key: getattr(vulnerability, key)
        for key in update_data
        if getattr(vulnerability, key) != update_data[key]
    }
    if before:
        vulnerability.sqlmodel_update(update_data)
        vulnerability.updated_at = get_datetime_utc()
        after = {key: getattr(vulnerability, key) for key in before}
        audit_log = AuditLog(
            actor_id=current_user.id,
            action=AuditAction.UPDATE,
            resource_type="vulnerability",
            resource_id=vulnerability.id,
            summary=f"Updated {vulnerability.cve_id}",
            changes={
                "before": _jsonable_changes(before),
                "after": _jsonable_changes(after),
            },
        )
        session.add(vulnerability)
        session.add(audit_log)
        session.commit()
        session.refresh(vulnerability)
    return vulnerability


@router.delete("/{vulnerability_id}")
def delete_vulnerability(
    session: SessionDep,
    current_user: CurrentSuperuser,
    vulnerability_id: uuid.UUID,
) -> Message:
    vulnerability = session.get(Vulnerability, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    audit_log = AuditLog(
        actor_id=current_user.id,
        action=AuditAction.DELETE,
        resource_type="vulnerability",
        resource_id=vulnerability.id,
        summary=f"Deleted {vulnerability.cve_id}",
        changes={"cve_id": vulnerability.cve_id},
    )
    session.add(audit_log)
    session.delete(vulnerability)
    session.commit()
    return Message(message="Vulnerability deleted successfully")


def _jsonable_changes(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat()
        if isinstance(value, datetime)
        else str(value)
        if isinstance(value, Decimal)
        else value.value
        if isinstance(value, Severity)
        else value
        for key, value in values.items()
    }


def _cve_id_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A vulnerability with this CVE ID already exists",
    )
