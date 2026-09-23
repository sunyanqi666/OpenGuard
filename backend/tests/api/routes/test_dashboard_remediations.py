import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.models import (
    AuditLog,
    Component,
    Remediation,
    Severity,
    Vulnerability,
    VulnerabilityComponent,
)


def test_dashboard_and_remediation_workflow(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = Vulnerability(cve_id="CVE-2096-7001", severity=Severity.CRITICAL)
    component = Component(
        purl="pkg:maven/org.example/stage-seven", name="stage-seven"
    )
    db.add(vulnerability)
    db.add(component)
    db.commit()
    db.refresh(vulnerability)
    db.refresh(component)
    association = VulnerabilityComponent(
        vulnerability_id=vulnerability.id,
        component_id=component.id,
        status="CONFIRMED",
        match_method="MANUAL",
    )
    db.add(association)
    db.commit()

    response = client.post(
        f"{settings.API_V1_STR}/remediations/",
        headers=superuser_token_headers,
        json={
            "vulnerability_id": str(vulnerability.id),
            "component_id": str(component.id),
            "status": "PENDING",
            "notes": "Needs review",
            "due_date": "2096-12-31",
        },
    )
    assert response.status_code == 201
    remediation_id = uuid.UUID(response.json()["id"])
    duplicate = client.post(
        f"{settings.API_V1_STR}/remediations/",
        headers=superuser_token_headers,
        json={
            "vulnerability_id": str(vulnerability.id),
            "component_id": str(component.id),
        },
    )
    assert duplicate.status_code == 409

    filtered = client.get(
        f"{settings.API_V1_STR}/remediations/",
        headers=superuser_token_headers,
        params={
            "search": "stage-seven",
            "severity": "CRITICAL",
            "status": "PENDING",
        },
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1
    assert filtered.json()["data"][0]["component_purl"] == component.purl

    overdue_update = client.patch(
        f"{settings.API_V1_STR}/remediations/{remediation_id}",
        headers=superuser_token_headers,
        json={"due_date": "2000-01-01"},
    )
    assert overdue_update.status_code == 200
    overdue = client.get(
        f"{settings.API_V1_STR}/remediations/",
        headers=superuser_token_headers,
        params={"overdue_only": True},
    )
    assert overdue.status_code == 200
    assert any(item["id"] == str(remediation_id) for item in overdue.json()["data"])
    summary = client.get(
        f"{settings.API_V1_STR}/remediations/summary",
        headers=superuser_token_headers,
    )
    assert summary.status_code == 200
    assert summary.json()["overdue"] >= 1
    assert summary.json()["pending"] >= 1

    updated = client.patch(
        f"{settings.API_V1_STR}/remediations/{remediation_id}",
        headers=superuser_token_headers,
        json={"status": "FIXED", "fixed_version": "2.0.0"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "FIXED"

    listed = client.get(
        f"{settings.API_V1_STR}/remediations/",
        headers=superuser_token_headers,
        params={"component_id": str(component.id)},
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    dashboard = client.get(
        f"{settings.API_V1_STR}/dashboard/summary",
        headers=superuser_token_headers,
    )
    assert dashboard.status_code == 200
    assert dashboard.json()["vulnerability_count"] >= 1
    assert any(
        item["component_id"] == str(component.id)
        for item in dashboard.json()["high_risk_components"]
    )

    removed = client.delete(
        f"{settings.API_V1_STR}/remediations/{remediation_id}",
        headers=superuser_token_headers,
    )
    assert removed.status_code == 200

    db.exec(delete(AuditLog).where(AuditLog.resource_id == remediation_id))
    db.exec(delete(Remediation).where(Remediation.id == remediation_id))
    db.exec(
        delete(VulnerabilityComponent).where(VulnerabilityComponent.id == association.id)
    )
    db.exec(delete(Vulnerability).where(Vulnerability.id == vulnerability.id))
    db.exec(delete(Component).where(Component.id == component.id))
    db.commit()


def test_remediation_write_requires_admin(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/remediations/",
        headers=normal_user_token_headers,
        json={
            "vulnerability_id": str(uuid.uuid4()),
            "component_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 403
