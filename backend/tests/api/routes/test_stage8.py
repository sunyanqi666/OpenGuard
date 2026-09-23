import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app import crud
from app.core.config import settings
from app.models import AuditLog, Component, User, UserCreate, UserRole


def test_component_csv_import_export_and_audit(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
) -> None:
    purl = "pkg:maven/org.example/stage-eight-import"
    content = (
        "purl,name,version,ecosystem,vendor,language\n"
        f"{purl},stage-eight-import,1.0.0,maven,org.example,java\n"
        "invalid,broken,1.0.0,maven,org.example,java\n"
    )
    response = client.post(
        f"{settings.API_V1_STR}/transfers/components/import",
        headers=superuser_token_headers,
        files={"file": ("components.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1
    assert response.json()["failed"] == 1

    exported = client.get(
        f"{settings.API_V1_STR}/transfers/components/export",
        headers=superuser_token_headers,
        params={"search": "stage-eight-import"},
    )
    assert exported.status_code == 200
    assert purl in exported.text
    assert "text/csv" in exported.headers["content-type"]

    audit = client.get(
        f"{settings.API_V1_STR}/audit-logs/",
        headers=superuser_token_headers,
        params={"resource_type": "component_import"},
    )
    assert audit.status_code == 200
    assert audit.json()["count"] >= 1

    component = db.exec(select(Component).where(Component.purl == purl)).one()
    db.exec(delete(AuditLog).where(AuditLog.resource_type == "component_import"))
    db.delete(component)
    db.commit()


def test_role_permissions(
    client: TestClient,
    normal_user_token_headers: dict[str, str],
    db: Session,
) -> None:
    forbidden = client.get(
        f"{settings.API_V1_STR}/audit-logs/", headers=normal_user_token_headers
    )
    assert forbidden.status_code == 403

    email = f"security-{uuid.uuid4()}@example.com"
    password = "Security-Role-2026!"
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=email, password=password, role=UserRole.SECURITY
        ),
    )
    login = client.post(
        f"{settings.API_V1_STR}/login/access-token",
        data={"username": email, "password": password},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get(f"{settings.API_V1_STR}/audit-logs/", headers=headers).status_code == 200
    assert client.post(
        f"{settings.API_V1_STR}/transfers/components/import",
        headers=headers,
        files={"file": ("components.csv", "purl,name\n", "text/csv")},
    ).status_code == 403
    db.exec(delete(User).where(User.id == user.id))
    db.commit()
