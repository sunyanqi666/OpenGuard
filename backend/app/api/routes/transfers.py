import csv
import io
import uuid
from typing import Any, TypedDict

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlmodel import col, select

from app.api.deps import CurrentSuperuser, CurrentUser, SessionDep
from app.models import (
    AuditAction,
    AuditLog,
    Component,
    ComponentImportResult,
    ImportIssue,
    Severity,
    Vulnerability,
    VulnerabilityComponent,
    get_datetime_utc,
    validate_component_name,
    validate_component_purl,
)

router = APIRouter(prefix="/transfers", tags=["transfers"])


class ComponentCsvValues(TypedDict):
    name: str
    version: str | None
    ecosystem: str | None
    vendor: str | None
    language: str | None
    repository: str | None
    description: str | None


@router.post("/components/import", response_model=ComponentImportResult)
async def import_components_csv(
    session: SessionDep,
    current_user: CurrentSuperuser,
    file: UploadFile = File(...),
) -> Any:
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only CSV files are supported")
    try:
        text = (await file.read()).decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="CSV must use UTF-8 encoding")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or not {"purl", "name"}.issubset(reader.fieldnames):
        raise HTTPException(
            status_code=422, detail="CSV must contain purl and name columns"
        )
    created = updated = skipped = failed = 0
    issues: list[ImportIssue] = []
    for row_number, row in enumerate(reader, start=2):
        try:
            purl = validate_component_purl(row.get("purl", ""))
            name = validate_component_name(row.get("name", ""))
            values: ComponentCsvValues = {
                "name": name,
                "version": row.get("version") or None,
                "ecosystem": row.get("ecosystem") or None,
                "vendor": row.get("vendor") or None,
                "language": row.get("language") or None,
                "repository": row.get("repository") or None,
                "description": row.get("description") or None,
            }
            component = session.exec(
                select(Component).where(Component.purl == purl)
            ).first()
            if component is None:
                session.add(Component(purl=purl, **values))
                created += 1
            else:
                changes = {
                    key: value
                    for key, value in values.items()
                    if getattr(component, key) != value
                }
                if changes:
                    component.sqlmodel_update(changes)
                    component.updated_at = get_datetime_utc()
                    session.add(component)
                    updated += 1
                else:
                    skipped += 1
        except ValueError as error:
            failed += 1
            issues.append(ImportIssue(row=row_number, message=str(error)))
    batch_id = uuid.uuid4()
    session.add(
        AuditLog(
            actor_id=current_user.id,
            action=AuditAction.CREATE,
            resource_type="component_import",
            resource_id=batch_id,
            summary=f"Imported components: {created} created, {updated} updated",
            changes={
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "failed": failed,
            },
        )
    )
    session.commit()
    return ComponentImportResult(
        created=created, updated=updated, skipped=skipped, failed=failed, issues=issues
    )


@router.get("/components/export")
def export_components_csv(
    session: SessionDep,
    _current_user: CurrentUser,
    search: str | None = Query(default=None, max_length=255),
    ecosystem: str | None = Query(default=None, max_length=64),
) -> StreamingResponse:
    filters: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                col(Component.purl).ilike(pattern),
                col(Component.name).ilike(pattern),
                col(Component.vendor).ilike(pattern),
            )
        )
    if ecosystem:
        filters.append(col(Component.ecosystem).ilike(ecosystem.strip()))
    rows = session.exec(
        select(Component).where(*filters).order_by(col(Component.name))
    ).all()
    return _csv_response(
        "components.csv",
        ["purl", "name", "version", "ecosystem", "vendor", "language", "repository"],
        [
            [
                item.purl,
                item.name,
                item.version,
                item.ecosystem,
                item.vendor,
                item.language,
                item.repository,
            ]
            for item in rows
        ],
    )


@router.get("/vulnerabilities/export")
def export_vulnerabilities_csv(
    session: SessionDep,
    _current_user: CurrentUser,
    search: str | None = Query(default=None, max_length=255),
    severity: Severity | None = None,
    high_risk_only: bool = False,
) -> StreamingResponse:
    filters: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                col(Vulnerability.cve_id).ilike(pattern),
                col(Vulnerability.title).ilike(pattern),
                col(Vulnerability.description).ilike(pattern),
            )
        )
    if severity:
        filters.append(Vulnerability.severity == severity)
    if high_risk_only:
        filters.append(
            col(Vulnerability.severity).in_([Severity.CRITICAL, Severity.HIGH])
        )
    rows = session.exec(
        select(Vulnerability).where(*filters).order_by(col(Vulnerability.cve_id))
    ).all()
    return _csv_response(
        "vulnerabilities.csv",
        ["cve_id", "severity", "cvss", "title", "published_at", "source"],
        [
            [
                item.cve_id,
                item.severity,
                item.cvss_score_v4 or item.cvss_score_v3 or item.cvss_score_v2,
                item.title,
                item.source_publish_date,
                item.source_name,
            ]
            for item in rows
        ],
    )


@router.get("/high-risk-components/export")
def export_high_risk_components(
    session: SessionDep, _current_user: CurrentUser
) -> StreamingResponse:
    rows = session.exec(
        select(Component, Vulnerability)
        .join(
            VulnerabilityComponent,
            col(Component.id) == col(VulnerabilityComponent.component_id),
        )
        .join(
            Vulnerability,
            col(Vulnerability.id) == col(VulnerabilityComponent.vulnerability_id),
        )
        .where(col(Vulnerability.severity).in_([Severity.CRITICAL, Severity.HIGH]))
        .order_by(col(Component.name), col(Vulnerability.cve_id))
    ).all()
    return _csv_response(
        "high-risk-components.csv",
        ["component", "purl", "cve_id", "severity"],
        [
            [
                component.name,
                component.purl,
                vulnerability.cve_id,
                vulnerability.severity,
            ]
            for component, vulnerability in rows
        ],
    )


def _csv_response(
    filename: str, headers: list[str], rows: list[list[Any]]
) -> StreamingResponse:
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
