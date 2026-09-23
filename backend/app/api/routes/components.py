import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentSuperuser, CurrentUser, SessionDep
from app.models import (
    AuditAction,
    AuditLog,
    Component,
    ComponentCreate,
    ComponentPublic,
    ComponentsPublic,
    ComponentUpdate,
    Message,
    get_datetime_utc,
)

router = APIRouter(prefix="/components", tags=["components"])


@router.get("/", response_model=ComponentsPublic)
def read_components(
    session: SessionDep,
    _current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, max_length=255),
    ecosystem: str | None = Query(default=None, max_length=64),
    language: str | None = Query(default=None, max_length=64),
    vendor: str | None = Query(default=None, max_length=255),
) -> Any:
    """Return an authenticated, filtered and paginated component list."""
    filters: list[Any] = []
    normalized_search = search.strip() if search else None
    if normalized_search:
        pattern = f"%{normalized_search}%"
        filters.append(
            or_(
                col(Component.purl).ilike(pattern),
                col(Component.name).ilike(pattern),
                col(Component.vendor).ilike(pattern),
                col(Component.description).ilike(pattern),
            )
        )
    if ecosystem:
        filters.append(col(Component.ecosystem).ilike(ecosystem.strip()))
    if language:
        filters.append(col(Component.language).ilike(language.strip()))
    if vendor:
        filters.append(col(Component.vendor).ilike(vendor.strip()))

    count = session.exec(
        select(func.count()).select_from(Component).where(*filters)
    ).one()
    statement = (
        select(Component)
        .where(*filters)
        .order_by(col(Component.name), col(Component.purl))
        .offset(skip)
        .limit(limit)
    )
    components = session.exec(statement).all()
    return ComponentsPublic(
        data=[ComponentPublic.model_validate(component) for component in components],
        count=count,
    )


@router.get("/{component_id}", response_model=ComponentPublic)
def read_component(
    session: SessionDep, _current_user: CurrentUser, component_id: uuid.UUID
) -> Any:
    component = session.get(Component, component_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Component not found")
    return component


@router.post("/", response_model=ComponentPublic, status_code=status.HTTP_201_CREATED)
def create_component(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    component_in: ComponentCreate,
) -> Any:
    if session.exec(
        select(Component).where(Component.purl == component_in.purl)
    ).first():
        raise _purl_conflict()

    component = Component.model_validate(component_in)
    audit_log = AuditLog(
        actor_id=current_user.id,
        action=AuditAction.CREATE,
        resource_type="component",
        resource_id=component.id,
        summary=f"Created {component.purl}",
        changes={"after": component_in.model_dump(mode="json")},
    )
    session.add(component)
    session.add(audit_log)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _purl_conflict()
    session.refresh(component)
    return component


@router.patch("/{component_id}", response_model=ComponentPublic)
def update_component(
    *,
    session: SessionDep,
    current_user: CurrentSuperuser,
    component_id: uuid.UUID,
    component_in: ComponentUpdate,
) -> Any:
    component = session.get(Component, component_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Component not found")

    update_data = component_in.model_dump(exclude_unset=True)
    for required_field in ("purl", "name"):
        if required_field in update_data and update_data[required_field] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{required_field} cannot be null",
            )
    new_purl = update_data.get("purl")
    if new_purl is not None and new_purl != component.purl:
        duplicate = session.exec(
            select(Component).where(Component.purl == new_purl)
        ).first()
        if duplicate is not None:
            raise _purl_conflict()

    before = {
        key: getattr(component, key)
        for key in update_data
        if getattr(component, key) != update_data[key]
    }
    if before:
        component.sqlmodel_update(update_data)
        component.updated_at = get_datetime_utc()
        after = {key: getattr(component, key) for key in before}
        audit_log = AuditLog(
            actor_id=current_user.id,
            action=AuditAction.UPDATE,
            resource_type="component",
            resource_id=component.id,
            summary=f"Updated {component.purl}",
            changes={
                "before": _jsonable_changes(before),
                "after": _jsonable_changes(after),
            },
        )
        session.add(component)
        session.add(audit_log)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise _purl_conflict()
        session.refresh(component)
    return component


@router.delete("/{component_id}")
def delete_component(
    session: SessionDep,
    current_user: CurrentSuperuser,
    component_id: uuid.UUID,
) -> Message:
    component = session.get(Component, component_id)
    if component is None:
        raise HTTPException(status_code=404, detail="Component not found")

    audit_log = AuditLog(
        actor_id=current_user.id,
        action=AuditAction.DELETE,
        resource_type="component",
        resource_id=component.id,
        summary=f"Deleted {component.purl}",
        changes={"purl": component.purl, "name": component.name},
    )
    session.add(audit_log)
    session.delete(component)
    session.commit()
    return Message(message="Component deleted successfully")


def _purl_conflict() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A component with this PURL already exists",
    )


def _jsonable_changes(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in values.items()
    }
