from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import (
    Component,
    ComponentCreate,
    Severity,
    Vulnerability,
    VulnerabilityCreate,
)


def test_vulnerability_normalizes_cve_id() -> None:
    vulnerability = VulnerabilityCreate(cve_id=" cve-2026-1234 ")

    assert vulnerability.cve_id == "CVE-2026-1234"
    assert vulnerability.severity == Severity.UNKNOWN


@pytest.mark.parametrize("cve_id", ["2026-1234", "CVE-26-1234", "CVE-2026-12AB"])
def test_vulnerability_rejects_invalid_cve_id(cve_id: str) -> None:
    with pytest.raises(ValidationError):
        VulnerabilityCreate(cve_id=cve_id)


@pytest.mark.parametrize("score", [Decimal("-0.1"), Decimal("10.1")])
def test_vulnerability_rejects_out_of_range_cvss(score: Decimal) -> None:
    with pytest.raises(ValidationError):
        VulnerabilityCreate(cve_id="CVE-2026-1234", cvss_score_v3=score)


def test_component_accepts_missing_version_from_teacher_data() -> None:
    component = ComponentCreate(purl="pkg:maven/org.example/demo", name="demo")

    assert component.version is None


@pytest.mark.parametrize("purl", ["org.example/demo", "pkg:maven"])
def test_component_rejects_invalid_purl(purl: str) -> None:
    with pytest.raises(ValidationError):
        ComponentCreate(purl=purl, name="demo")


def test_database_rejects_duplicate_cve_id(db: Session) -> None:
    first = Vulnerability(cve_id="CVE-2099-1001")
    db.add(first)
    db.commit()

    db.add(Vulnerability(cve_id="CVE-2099-1001"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.delete(first)
    db.commit()


def test_database_rejects_duplicate_purl(db: Session) -> None:
    first = Component(purl="pkg:maven/org.example/unique-test", name="unique-test")
    db.add(first)
    db.commit()

    db.add(Component(purl=first.purl, name="duplicate"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.delete(first)
    db.commit()
