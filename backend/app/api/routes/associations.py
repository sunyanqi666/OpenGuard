import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentSecurityEditor, CurrentUser, SessionDep
from app.models import (
    AssociationStatus,
    AssociationSuggestion,
    AuditAction,
    AuditLog,
    Component,
    ComponentPublic,
    MatchMethod,
    Message,
    Vulnerability,
    VulnerabilityComponent,
    VulnerabilityComponentCreate,
    VulnerabilityComponentPublic,
    VulnerabilityComponentsPublic,
)

router = APIRouter(prefix="/associations", tags=["associations"])


@router.get("/", response_model=VulnerabilityComponentsPublic)
def read_associations(
    session: SessionDep,
    _current_user: CurrentUser,
    vulnerability_id: uuid.UUID | None = None,
    component_id: uuid.UUID | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> Any:
    filters: list[Any] = []
    if vulnerability_id:
        filters.append(VulnerabilityComponent.vulnerability_id == vulnerability_id)
    if component_id:
        filters.append(VulnerabilityComponent.component_id == component_id)

    count = session.exec(
        select(func.count()).select_from(VulnerabilityComponent).where(*filters)
    ).one()
    statement = (
        select(VulnerabilityComponent, Vulnerability, Component)
        .join(Vulnerability)
        .join(Component)
        .where(*filters)
        .order_by(col(VulnerabilityComponent.created_at).desc())
        .offset(skip)
        .limit(limit)
    )
    return VulnerabilityComponentsPublic(
        data=[_to_public(*row) for row in session.exec(statement).all()], count=count
    )


@router.get("/suggestions", response_model=list[AssociationSuggestion])
def read_association_suggestions(
    session: SessionDep,
    _current_user: CurrentUser,
    vulnerability_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=50),
) -> Any:
    vulnerability = session.get(Vulnerability, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")

    existing_ids = select(VulnerabilityComponent.component_id).where(
        VulnerabilityComponent.vulnerability_id == vulnerability_id
    )
    text = " ".join(
        value
        for value in (
            vulnerability.title,
            vulnerability.description,
            vulnerability.vulnerability_type,
            vulnerability.source_id,
        )
        if value
    ).lower()
    candidates = session.exec(
        select(Component)
        .where(col(Component.id).not_in(existing_ids))
        .order_by(col(Component.name))
    ).all()
    suggestions: list[AssociationSuggestion] = []
    for component in candidates:
        match = _match_component(component, text)
        if match:
            method, confidence, reason = match
            suggestions.append(
                AssociationSuggestion(
                    component=ComponentPublic.model_validate(component),
                    match_method=method,
                    confidence=confidence,
                    reason=reason,
                )
            )
    suggestions.sort(key=lambda item: item.confidence, reverse=True)
    return suggestions[:limit]


@router.post(
    "/",
    response_model=VulnerabilityComponentPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_association(
    *,
    session: SessionDep,
    current_user: CurrentSecurityEditor,
    association_in: VulnerabilityComponentCreate,
) -> Any:
    vulnerability = session.get(Vulnerability, association_in.vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    component = session.get(Component, association_in.component_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Component not found")
    duplicate = session.exec(
        select(VulnerabilityComponent).where(
            VulnerabilityComponent.vulnerability_id == association_in.vulnerability_id,
            VulnerabilityComponent.component_id == association_in.component_id,
        )
    ).first()
    if duplicate:
        raise _association_conflict()

    association = VulnerabilityComponent.model_validate(
        association_in,
        update={
            "status": AssociationStatus.CONFIRMED,
            "confirmed_by_id": current_user.id,
            "confidence": Decimal("1.000")
            if association_in.match_method == MatchMethod.MANUAL
            else None,
        },
    )
    session.add(association)
    session.add(
        AuditLog(
            actor_id=current_user.id,
            action=AuditAction.LINK,
            resource_type="vulnerability_component",
            resource_id=association.id,
            summary=f"Linked {vulnerability.cve_id} to {component.purl}",
            changes={"after": association_in.model_dump(mode="json")},
        )
    )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _association_conflict()
    session.refresh(association)
    return _to_public(association, vulnerability, component)


@router.delete("/{association_id}")
def delete_association(
    session: SessionDep,
    current_user: CurrentSecurityEditor,
    association_id: uuid.UUID,
) -> Message:
    association = session.get(VulnerabilityComponent, association_id)
    if association is None:
        raise HTTPException(status_code=404, detail="Association not found")
    vulnerability = session.get(Vulnerability, association.vulnerability_id)
    component = session.get(Component, association.component_id)
    session.add(
        AuditLog(
            actor_id=current_user.id,
            action=AuditAction.UNLINK,
            resource_type="vulnerability_component",
            resource_id=association.id,
            summary="Unlinked vulnerability and component",
            changes={
                "vulnerability_id": str(association.vulnerability_id),
                "component_id": str(association.component_id),
                "cve_id": vulnerability.cve_id if vulnerability else None,
                "component_purl": component.purl if component else None,
            },
        )
    )
    session.delete(association)
    session.commit()
    return Message(message="Association deleted successfully")


def _to_public(
    association: VulnerabilityComponent,
    vulnerability: Vulnerability,
    component: Component,
) -> VulnerabilityComponentPublic:
    return VulnerabilityComponentPublic(
        **association.model_dump(exclude={"status", "match_method"}),
        status=AssociationStatus(association.status),
        match_method=MatchMethod(association.match_method),
        cve_id=vulnerability.cve_id,
        severity=vulnerability.severity,
        component_name=component.name,
        component_purl=component.purl,
    )


def _match_component(
    component: Component, text: str
) -> tuple[MatchMethod, Decimal, str] | None:
    if component.cpe:
        cpe_parts = [
            part for part in component.cpe.lower().split(":") if len(part) >= 3
        ]
        matched = next((part for part in reversed(cpe_parts) if part in text), None)
        if matched:
            return (
                MatchMethod.CPE,
                Decimal("0.900"),
                f"CPE 特征“{matched}”出现在漏洞信息中",
            )
    name = component.name.strip().lower()
    if len(name) >= 3 and name in text:
        return (
            MatchMethod.NAME,
            Decimal("0.750"),
            f"组件名称“{component.name}”出现在漏洞信息中",
        )
    vendor = (component.vendor or "").strip().lower()
    if len(vendor) >= 3 and vendor in text:
        return (
            MatchMethod.NAME,
            Decimal("0.600"),
            f"厂商“{component.vendor}”出现在漏洞信息中",
        )
    return None


def _association_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="This vulnerability and component are already associated",
    )
