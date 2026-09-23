from pathlib import Path

from sqlmodel import Session, delete, select

from app.data_import import import_components, import_vulnerabilities
from app.models import Component, Vulnerability

VULNERABILITY_SQL = """
INSERT INTO osscore.tmp_vul (source_id, source_name, source_publish_date,
source_update_date, source_link, affected_version, cvss_score_v4,
cvss_score_v3, cvss_score_v2, severity, type, cwe_id, description, cve_id,
title) VALUES ('CVE-2098-1001', 'NVD', '2026-01-02 03:04:05', null,
'https://example.com/CVE-2098-1001', '[\"cpe:2.3:a:example:demo:*\"]', null,
8.8, null, 'HIGH', null, '[\"CWE-79\"]', 'It\\'s multiline;
and keeps the semicolon.', 'CVE-2098-1001', null);
"""

COMPONENT_SQL = """
INSERT INTO osscore.tmp_comp (purl, cpe, type, vendor, name, version, license,
description, repository, publish_date, language, record_time) VALUES
('pkg:maven/org.example/import-test', '', 'maven', 'org.example', 'import-test',
'', '', 'Teacher component', '', null, 'java', '2024-07-26 00:00:00');
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_imports_teacher_rows_and_normalizes_values(
    db: Session, tmp_path: Path
) -> None:
    vulnerability_path = _write(tmp_path / "vul.sql", VULNERABILITY_SQL)
    component_path = _write(tmp_path / "comp.sql", COMPONENT_SQL)

    vulnerability_report = import_vulnerabilities(db, vulnerability_path)
    component_report = import_components(db, component_path)
    db.commit()

    assert vulnerability_report.inserted == 1
    assert vulnerability_report.failed == 0
    assert component_report.inserted == 1
    assert component_report.failed == 0

    vulnerability = db.exec(
        select(Vulnerability).where(Vulnerability.cve_id == "CVE-2098-1001")
    ).one()
    component = db.exec(
        select(Component).where(
            Component.purl == "pkg:maven/org.example/import-test"
        )
    ).one()
    assert vulnerability.description == "It's multiline;\nand keeps the semicolon."
    assert vulnerability.affected_versions == ["cpe:2.3:a:example:demo:*"]
    assert vulnerability.cwe_ids == ["CWE-79"]
    assert component.version is None
    assert component.cpe is None
    assert component.source_record_time is not None

    db.exec(
        delete(Vulnerability).where(Vulnerability.cve_id == "CVE-2098-1001")
    )
    db.exec(
        delete(Component).where(
            Component.purl == "pkg:maven/org.example/import-test"
        )
    )
    db.commit()


def test_repeated_import_is_idempotent(db: Session, tmp_path: Path) -> None:
    vulnerability_path = _write(tmp_path / "vul.sql", VULNERABILITY_SQL)
    component_path = _write(tmp_path / "comp.sql", COMPONENT_SQL)

    import_vulnerabilities(db, vulnerability_path)
    import_components(db, component_path)
    db.commit()
    vulnerability_report = import_vulnerabilities(db, vulnerability_path)
    component_report = import_components(db, component_path)

    assert vulnerability_report.inserted == 0
    assert vulnerability_report.updated == 0
    assert vulnerability_report.unchanged == 1
    assert component_report.inserted == 0
    assert component_report.updated == 0
    assert component_report.unchanged == 1

    db.exec(
        delete(Vulnerability).where(Vulnerability.cve_id == "CVE-2098-1001")
    )
    db.exec(
        delete(Component).where(
            Component.purl == "pkg:maven/org.example/import-test"
        )
    )
    db.commit()


def test_invalid_json_is_reported_without_insert(db: Session, tmp_path: Path) -> None:
    invalid_sql = VULNERABILITY_SQL.replace(
        "'[\"CWE-79\"]'", "'not-json'"
    ).replace("CVE-2098-1001", "CVE-2098-1002")
    report = import_vulnerabilities(db, _write(tmp_path / "invalid.sql", invalid_sql))

    assert report.total == 1
    assert report.failed == 1
    assert report.inserted == 0
    assert report.errors
