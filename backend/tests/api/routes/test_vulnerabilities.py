import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.models import (
    AssociationStatus,
    AuditAction,
    AuditLog,
    Component,
    MatchMethod,
    Remediation,
    Severity,
    Vulnerability,
    VulnerabilityComponent,
)


def create_vulnerability(
    db: Session,
    *,
    cve_id: str,
    severity: Severity = Severity.HIGH,
    cvss: Decimal = Decimal("8.0"),
    description: str | None = None,
    published_at: datetime | None = None,
) -> Vulnerability:
    vulnerability = Vulnerability(
        cve_id=cve_id,
        source_name="NVD",
        source_publish_date=published_at or datetime(2026, 1, 1, tzinfo=UTC),
        cvss_score_v3=cvss,
        severity=severity,
        description=description,
    )
    db.add(vulnerability)
    db.commit()
    db.refresh(vulnerability)
    return vulnerability


def cleanup_vulnerabilities(db: Session, *vulnerability_ids: uuid.UUID) -> None:
    db.exec(delete(AuditLog).where(AuditLog.resource_id.in_(vulnerability_ids)))
    db.exec(delete(Vulnerability).where(Vulnerability.id.in_(vulnerability_ids)))
    db.commit()


def test_read_vulnerabilities_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/vulnerabilities/")

    assert response.status_code == 401


def test_create_vulnerability_creates_record_and_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=superuser_token_headers,
        json={
            "cve_id": "cve-2097-1001",
            "source_name": "MANUAL",
            "severity": "HIGH",
            "cvss_score_v3": 8.2,
            "title": "Manual CVE test",
        },
    )
    assert response.status_code == 201
    content = response.json()
    assert content["cve_id"] == "CVE-2097-1001"
    vulnerability_id = uuid.UUID(content["id"])
    assert db.exec(
        select(AuditLog).where(
            AuditLog.resource_id == vulnerability_id,
            AuditLog.action == AuditAction.CREATE,
        )
    ).one()
    cleanup_vulnerabilities(db, vulnerability_id)


def test_create_vulnerability_rejects_duplicate_invalid_and_non_admin(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1002")
    duplicate = client.post(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=superuser_token_headers,
        json={"cve_id": vulnerability.cve_id},
    )
    assert duplicate.status_code == 409
    invalid = client.post(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=superuser_token_headers,
        json={"cve_id": "not-a-cve"},
    )
    assert invalid.status_code == 422
    forbidden = client.post(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=normal_user_token_headers,
        json={"cve_id": "CVE-2097-1003"},
    )
    assert forbidden.status_code == 403
    cleanup_vulnerabilities(db, vulnerability.id)


def test_read_vulnerabilities_paginates_and_filters(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    high = create_vulnerability(
        db,
        cve_id="CVE-2097-1101",
        severity=Severity.HIGH,
        cvss=Decimal("8.8"),
        description="stage-three-filter-unique browser sandbox issue",
        published_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    low = create_vulnerability(
        db,
        cve_id="CVE-2097-1102",
        severity=Severity.LOW,
        cvss=Decimal("3.1"),
        description="stage-three-filter-unique local issue",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    medium = create_vulnerability(
        db,
        cve_id="CVE-2097-1103",
        severity=Severity.MEDIUM,
        cvss=Decimal("5.5"),
        description="Unrelated test record",
        published_at=datetime(2025, 12, 31, tzinfo=UTC),
    )

    response = client.get(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=normal_user_token_headers,
        params={"search": "stage-three-filter-unique", "skip": 0, "limit": 1},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 2
    assert len(content["data"]) == 1
    assert content["data"][0]["cve_id"] == high.cve_id

    response = client.get(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=normal_user_token_headers,
        params={
            "severity": "HIGH",
            "search": "stage-three-filter-unique",
            "source_name": "nvd",
            "min_cvss": "8.0",
            "max_cvss": "9.0",
            "published_from": "2026-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 200
    assert [item["cve_id"] for item in response.json()["data"]] == [high.cve_id]

    cleanup_vulnerabilities(db, high.id, low.id, medium.id)


def test_read_vulnerabilities_rejects_inverted_ranges(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=normal_user_token_headers,
        params={"min_cvss": "9", "max_cvss": "2"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "min_cvss must not be greater than max_cvss"

    response = client.get(
        f"{settings.API_V1_STR}/vulnerabilities/",
        headers=normal_user_token_headers,
        params={
            "published_from": "2026-02-01T00:00:00Z",
            "published_to": "2026-01-01T00:00:00Z",
        },
    )
    assert response.status_code == 422


def test_read_vulnerability_and_not_found(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1201")

    response = client.get(
        f"{settings.API_V1_STR}/vulnerabilities/{vulnerability.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["cve_id"] == vulnerability.cve_id

    response = client.get(
        f"{settings.API_V1_STR}/vulnerabilities/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404

    cleanup_vulnerabilities(db, vulnerability.id)


def test_update_vulnerability_creates_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1301")
    original_updated_at = vulnerability.updated_at

    response = client.patch(
        f"{settings.API_V1_STR}/vulnerabilities/{vulnerability.id}",
        headers=superuser_token_headers,
        json={
            "severity": "CRITICAL",
            "cvss_score_v3": 9.8,
            "title": "Updated vulnerability",
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["severity"] == "CRITICAL"
    assert content["title"] == "Updated vulnerability"
    assert datetime.fromisoformat(content["updated_at"]) >= original_updated_at

    audit_log = db.exec(
        select(AuditLog).where(
            AuditLog.resource_id == vulnerability.id,
            AuditLog.action == AuditAction.UPDATE,
        )
    ).one()
    assert audit_log.changes["before"]["severity"] == "HIGH"
    assert audit_log.changes["after"]["severity"] == "CRITICAL"

    cleanup_vulnerabilities(db, vulnerability.id)


def test_update_vulnerability_rejects_invalid_or_immutable_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1302")
    url = f"{settings.API_V1_STR}/vulnerabilities/{vulnerability.id}"

    assert (
        client.patch(
            url, headers=superuser_token_headers, json={"cvss_score_v3": 10.1}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            url, headers=superuser_token_headers, json={"severity": "EXTREME"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            url, headers=superuser_token_headers, json={"severity": None}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            url,
            headers=superuser_token_headers,
            json={"cve_id": "CVE-2097-9999"},
        ).status_code
        == 422
    )

    cleanup_vulnerabilities(db, vulnerability.id)


def test_update_vulnerability_requires_superuser(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1303")
    response = client.patch(
        f"{settings.API_V1_STR}/vulnerabilities/{vulnerability.id}",
        headers=normal_user_token_headers,
        json={"title": "Forbidden update"},
    )

    assert response.status_code == 403
    cleanup_vulnerabilities(db, vulnerability.id)


def test_update_vulnerability_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.patch(
        f"{settings.API_V1_STR}/vulnerabilities/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"title": "Missing"},
    )

    assert response.status_code == 404


def test_delete_vulnerability_cascades_and_creates_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1401")
    component = Component(
        purl="pkg:maven/org.example/cascade-test", name="cascade-test"
    )
    db.add(component)
    db.commit()
    db.refresh(component)
    association = VulnerabilityComponent(
        vulnerability_id=vulnerability.id,
        component_id=component.id,
        status=AssociationStatus.CONFIRMED,
        match_method=MatchMethod.MANUAL,
    )
    remediation = Remediation(
        vulnerability_id=vulnerability.id, component_id=component.id
    )
    db.add(association)
    db.add(remediation)
    db.commit()
    vulnerability_id = vulnerability.id
    association_id = association.id
    remediation_id = remediation.id

    response = client.delete(
        f"{settings.API_V1_STR}/vulnerabilities/{vulnerability_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Vulnerability deleted successfully"
    db.expire_all()
    assert db.get(Vulnerability, vulnerability_id) is None
    assert db.get(VulnerabilityComponent, association_id) is None
    assert db.get(Remediation, remediation_id) is None
    assert db.exec(
        select(AuditLog).where(
            AuditLog.resource_id == vulnerability_id,
            AuditLog.action == AuditAction.DELETE,
        )
    ).one()

    db.exec(delete(AuditLog).where(AuditLog.resource_id == vulnerability_id))
    db.delete(component)
    db.commit()


def test_delete_vulnerability_requires_superuser(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = create_vulnerability(db, cve_id="CVE-2097-1402")
    response = client.delete(
        f"{settings.API_V1_STR}/vulnerabilities/{vulnerability.id}",
        headers=normal_user_token_headers,
    )

    assert response.status_code == 403
    cleanup_vulnerabilities(db, vulnerability.id)


def test_delete_vulnerability_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.delete(
        f"{settings.API_V1_STR}/vulnerabilities/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )

    assert response.status_code == 404
