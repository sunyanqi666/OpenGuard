import uuid

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
    Vulnerability,
    VulnerabilityComponent,
)


def create_component(
    db: Session,
    *,
    purl: str,
    name: str,
    ecosystem: str | None = "maven",
    language: str | None = "java",
    vendor: str | None = "org.example",
) -> Component:
    component = Component(
        purl=purl,
        name=name,
        ecosystem=ecosystem,
        language=language,
        vendor=vendor,
    )
    db.add(component)
    db.commit()
    db.refresh(component)
    return component


def cleanup_components(db: Session, *component_ids: uuid.UUID) -> None:
    db.exec(delete(AuditLog).where(AuditLog.resource_id.in_(component_ids)))
    db.exec(delete(Component).where(Component.id.in_(component_ids)))
    db.commit()


def test_read_components_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{settings.API_V1_STR}/components/")

    assert response.status_code == 401


def test_read_components_paginates_and_filters(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    alpha = create_component(
        db,
        purl="pkg:maven/org.example/filter-alpha",
        name="filter-alpha",
    )
    beta = create_component(
        db,
        purl="pkg:npm/filter-beta/package",
        name="filter-beta",
        ecosystem="npm",
        language="typescript",
        vendor="filter-vendor",
    )
    gamma = create_component(
        db,
        purl="pkg:maven/org.other/unrelated",
        name="unrelated",
        vendor="org.other",
    )

    response = client.get(
        f"{settings.API_V1_STR}/components/",
        headers=normal_user_token_headers,
        params={"search": "filter-", "skip": 0, "limit": 1},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 2
    assert len(content["data"]) == 1
    assert content["data"][0]["name"] == alpha.name

    response = client.get(
        f"{settings.API_V1_STR}/components/",
        headers=normal_user_token_headers,
        params={
            "ecosystem": "NPM",
            "language": "TypeScript",
            "vendor": "FILTER-VENDOR",
        },
    )
    assert response.status_code == 200
    assert [item["purl"] for item in response.json()["data"]] == [beta.purl]

    cleanup_components(db, alpha.id, beta.id, gamma.id)


def test_read_component_and_not_found(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    component = create_component(
        db, purl="pkg:maven/org.example/detail", name="detail"
    )

    response = client.get(
        f"{settings.API_V1_STR}/components/{component.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["purl"] == component.purl

    response = client.get(
        f"{settings.API_V1_STR}/components/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 404

    cleanup_components(db, component.id)


def test_create_component_and_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    payload = {
        "purl": "pkg:maven/org.example/api-create",
        "name": " api-create ",
        "version": "1.0.0",
        "ecosystem": "maven",
        "repository": "https://github.com/example/api-create",
    }
    response = client.post(
        f"{settings.API_V1_STR}/components/",
        headers=superuser_token_headers,
        json=payload,
    )

    assert response.status_code == 201
    content = response.json()
    assert content["name"] == "api-create"
    component_id = uuid.UUID(content["id"])
    audit_log = db.exec(
        select(AuditLog).where(
            AuditLog.resource_id == component_id,
            AuditLog.action == AuditAction.CREATE,
        )
    ).one()
    assert audit_log.changes["after"]["purl"] == payload["purl"]

    cleanup_components(db, component_id)


def test_create_component_rejects_duplicate_purl(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    component = create_component(
        db, purl="pkg:maven/org.example/duplicate", name="duplicate"
    )
    response = client.post(
        f"{settings.API_V1_STR}/components/",
        headers=superuser_token_headers,
        json={"purl": component.purl, "name": "another"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "A component with this PURL already exists"
    cleanup_components(db, component.id)


def test_create_component_validates_fields(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    url = f"{settings.API_V1_STR}/components/"
    for payload in (
        {"purl": "not-a-purl", "name": "demo"},
        {"purl": "pkg:maven/org.example/blank", "name": "   "},
        {
            "purl": "pkg:maven/org.example/url",
            "name": "url",
            "repository": "ftp://example.com/repository",
        },
    ):
        response = client.post(url, headers=superuser_token_headers, json=payload)
        assert response.status_code == 422


def test_create_component_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/components/",
        headers=normal_user_token_headers,
        json={"purl": "pkg:maven/org.example/forbidden", "name": "forbidden"},
    )

    assert response.status_code == 403


def test_update_component_and_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    component = create_component(
        db, purl="pkg:maven/org.example/update", name="before"
    )
    response = client.patch(
        f"{settings.API_V1_STR}/components/{component.id}",
        headers=superuser_token_headers,
        json={
            "name": " after ",
            "version": "2.0.0",
            "repository": "https://example.com/repository",
        },
    )

    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "after"
    assert content["version"] == "2.0.0"
    audit_log = db.exec(
        select(AuditLog).where(
            AuditLog.resource_id == component.id,
            AuditLog.action == AuditAction.UPDATE,
        )
    ).one()
    assert audit_log.changes["before"]["name"] == "before"
    assert audit_log.changes["after"]["name"] == "after"

    cleanup_components(db, component.id)


def test_update_component_rejects_duplicate_and_null_required_fields(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    first = create_component(
        db, purl="pkg:maven/org.example/update-first", name="first"
    )
    second = create_component(
        db, purl="pkg:maven/org.example/update-second", name="second"
    )
    url = f"{settings.API_V1_STR}/components/{second.id}"

    assert (
        client.patch(
            url, headers=superuser_token_headers, json={"purl": first.purl}
        ).status_code
        == 409
    )
    assert (
        client.patch(url, headers=superuser_token_headers, json={"purl": None})
        .status_code
        == 422
    )
    assert (
        client.patch(url, headers=superuser_token_headers, json={"name": None})
        .status_code
        == 422
    )

    cleanup_components(db, first.id, second.id)


def test_update_component_permissions_and_not_found(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    component = create_component(
        db, purl="pkg:maven/org.example/update-permission", name="permission"
    )
    response = client.patch(
        f"{settings.API_V1_STR}/components/{component.id}",
        headers=normal_user_token_headers,
        json={"name": "forbidden"},
    )
    assert response.status_code == 403

    response = client.patch(
        f"{settings.API_V1_STR}/components/{uuid.uuid4()}",
        headers=superuser_token_headers,
        json={"name": "missing"},
    )
    assert response.status_code == 404
    cleanup_components(db, component.id)


def test_delete_component_cascades_and_creates_audit_log(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    vulnerability = Vulnerability(cve_id="CVE-2096-1501")
    component = create_component(
        db, purl="pkg:maven/org.example/delete-cascade", name="delete-cascade"
    )
    db.add(vulnerability)
    db.commit()
    db.refresh(vulnerability)
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
    component_id = component.id
    association_id = association.id
    remediation_id = remediation.id

    response = client.delete(
        f"{settings.API_V1_STR}/components/{component_id}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Component deleted successfully"
    db.expire_all()
    assert db.get(Component, component_id) is None
    assert db.get(VulnerabilityComponent, association_id) is None
    assert db.get(Remediation, remediation_id) is None
    assert db.exec(
        select(AuditLog).where(
            AuditLog.resource_id == component_id,
            AuditLog.action == AuditAction.DELETE,
        )
    ).one()

    db.exec(delete(AuditLog).where(AuditLog.resource_id == component_id))
    db.delete(vulnerability)
    db.commit()


def test_delete_component_permissions_and_not_found(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    component = create_component(
        db, purl="pkg:maven/org.example/delete-permission", name="permission"
    )
    response = client.delete(
        f"{settings.API_V1_STR}/components/{component.id}",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403

    response = client.delete(
        f"{settings.API_V1_STR}/components/{uuid.uuid4()}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    cleanup_components(db, component.id)
