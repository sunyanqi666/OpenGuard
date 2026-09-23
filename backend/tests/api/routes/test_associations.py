import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.models import (
    AuditAction,
    AuditLog,
    Component,
    Severity,
    Vulnerability,
    VulnerabilityComponent,
)


def make_records(db: Session, suffix: str) -> tuple[Vulnerability, Component]:
    vulnerability = Vulnerability(
        cve_id=f"CVE-2098-{suffix}",
        severity=Severity.HIGH,
        title="Critical example-widget issue",
        description="The org.example example-widget package is affected.",
    )
    component = Component(
        purl=f"pkg:maven/org.example/example-widget-{suffix}",
        name="example-widget",
        vendor="org.example",
        ecosystem="maven",
        language="java",
    )
    db.add(vulnerability)
    db.add(component)
    db.commit()
    db.refresh(vulnerability)
    db.refresh(component)
    return vulnerability, component


def cleanup(db: Session, vulnerability_id: uuid.UUID, component_id: uuid.UUID) -> None:
    association_ids = db.exec(
        select(VulnerabilityComponent.id).where(
            VulnerabilityComponent.vulnerability_id == vulnerability_id
        )
    ).all()
    if association_ids:
        db.exec(delete(AuditLog).where(AuditLog.resource_id.in_(association_ids)))
    for audit_log in db.exec(
        select(AuditLog).where(
            AuditLog.resource_type == "vulnerability_component"
        )
    ).all():
        serialized_changes = str(audit_log.changes)
        if (
            str(vulnerability_id) in serialized_changes
            or str(component_id) in serialized_changes
        ):
            db.delete(audit_log)
    db.exec(
        delete(VulnerabilityComponent).where(
            VulnerabilityComponent.vulnerability_id == vulnerability_id
        )
    )
    db.exec(delete(Vulnerability).where(Vulnerability.id == vulnerability_id))
    db.exec(delete(Component).where(Component.id == component_id))
    db.commit()


def test_association_crud_is_bidirectional_and_audited(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability, component = make_records(db, "9001")
    response = client.post(
        f"{settings.API_V1_STR}/associations/",
        headers=superuser_token_headers,
        json={
            "vulnerability_id": str(vulnerability.id),
            "component_id": str(component.id),
            "affected_version_range": "[1.0,2.0)",
            "source_reference": "teacher-dataset",
            "notes": "manual confirmation",
            "match_method": "MANUAL",
        },
    )
    assert response.status_code == 201
    content = response.json()
    assert content["status"] == "CONFIRMED"
    assert content["cve_id"] == vulnerability.cve_id
    assert content["component_purl"] == component.purl
    association_id = uuid.UUID(content["id"])

    for params in (
        {"vulnerability_id": str(vulnerability.id)},
        {"component_id": str(component.id)},
    ):
        listed = client.get(
            f"{settings.API_V1_STR}/associations/",
            headers=superuser_token_headers,
            params=params,
        )
        assert listed.status_code == 200
        assert listed.json()["count"] == 1
        assert listed.json()["data"][0]["id"] == str(association_id)

    duplicate = client.post(
        f"{settings.API_V1_STR}/associations/",
        headers=superuser_token_headers,
        json={
            "vulnerability_id": str(vulnerability.id),
            "component_id": str(component.id),
        },
    )
    assert duplicate.status_code == 409

    removed = client.delete(
        f"{settings.API_V1_STR}/associations/{association_id}",
        headers=superuser_token_headers,
    )
    assert removed.status_code == 200
    actions = db.exec(
        select(AuditLog.action).where(AuditLog.resource_id == association_id)
    ).all()
    assert actions == [AuditAction.LINK, AuditAction.UNLINK]
    cleanup(db, vulnerability.id, component.id)


def test_suggestions_exclude_existing_associations(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability, component = make_records(db, "9002")
    response = client.get(
        f"{settings.API_V1_STR}/associations/suggestions",
        headers=superuser_token_headers,
        params={"vulnerability_id": str(vulnerability.id)},
    )
    assert response.status_code == 200
    suggested = next(
        item for item in response.json() if item["component"]["id"] == str(component.id)
    )
    assert suggested["match_method"] == "NAME"

    client.post(
        f"{settings.API_V1_STR}/associations/",
        headers=superuser_token_headers,
        json={
            "vulnerability_id": str(vulnerability.id),
            "component_id": str(component.id),
            "match_method": suggested["match_method"],
        },
    )
    response = client.get(
        f"{settings.API_V1_STR}/associations/suggestions",
        headers=superuser_token_headers,
        params={"vulnerability_id": str(vulnerability.id)},
    )
    assert all(
        item["component"]["id"] != str(component.id) for item in response.json()
    )
    cleanup(db, vulnerability.id, component.id)


def test_association_permissions_and_not_found(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability, component = make_records(db, "9003")
    response = client.post(
        f"{settings.API_V1_STR}/associations/",
        headers=normal_user_token_headers,
        json={
            "vulnerability_id": str(vulnerability.id),
            "component_id": str(component.id),
        },
    )
    assert response.status_code == 403

    response = client.post(
        f"{settings.API_V1_STR}/associations/",
        headers=superuser_token_headers,
        json={
            "vulnerability_id": str(uuid.uuid4()),
            "component_id": str(component.id),
        },
    )
    assert response.status_code == 404
    response = client.delete(
        f"{settings.API_V1_STR}/associations/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    cleanup(db, vulnerability.id, component.id)
