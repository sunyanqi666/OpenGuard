import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session, select

from app.models import (
    Component,
    ComponentCreate,
    Severity,
    Vulnerability,
    VulnerabilityCreate,
    get_datetime_utc,
)

VULNERABILITY_COLUMNS = (
    "source_id",
    "source_name",
    "source_publish_date",
    "source_update_date",
    "source_link",
    "affected_version",
    "cvss_score_v4",
    "cvss_score_v3",
    "cvss_score_v2",
    "severity",
    "type",
    "cwe_id",
    "description",
    "cve_id",
    "title",
)

COMPONENT_COLUMNS = (
    "purl",
    "cpe",
    "type",
    "vendor",
    "name",
    "version",
    "license",
    "description",
    "repository",
    "publish_date",
    "language",
    "record_time",
)


@dataclass
class ImportReport:
    source: str
    total: int = 0
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def add_error(self, row_number: int, error: Exception | str) -> None:
        self.failed += 1
        if len(self.errors) < 20:
            self.errors.append(f"row {row_number}: {error}")


def _split_sql_statements(sql: str) -> Iterator[str]:
    buffer: list[str] = []
    in_quote = False
    index = 0
    while index < len(sql):
        char = sql[index]
        buffer.append(char)
        if in_quote and char == "\\" and index + 1 < len(sql):
            index += 1
            buffer.append(sql[index])
        elif char == "'":
            if in_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 1
                buffer.append(sql[index])
            else:
                in_quote = not in_quote
        elif char == ";" and not in_quote:
            yield "".join(buffer)
            buffer = []
        index += 1
    if "".join(buffer).strip():
        yield "".join(buffer)


def _decode_mysql_escape(char: str) -> str:
    return {
        "0": "\0",
        "b": "\b",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "Z": "\x1a",
    }.get(char, char)


def _parse_values(statement: str) -> list[str | None]:
    match = re.search(r"\bVALUES\s*\(", statement, flags=re.IGNORECASE)
    if not match:
        raise ValueError("INSERT statement has no VALUES tuple")

    raw = statement[match.end() :].rstrip().removesuffix(";").rstrip()
    if not raw.endswith(")"):
        raise ValueError("VALUES tuple is not closed")
    raw = raw[:-1]

    values: list[str | None] = []
    buffer: list[str] = []
    in_quote = False
    quoted_value = False
    index = 0
    while index < len(raw):
        char = raw[index]
        if in_quote:
            if char == "\\" and index + 1 < len(raw):
                index += 1
                buffer.append(_decode_mysql_escape(raw[index]))
            elif char == "'":
                if index + 1 < len(raw) and raw[index + 1] == "'":
                    buffer.append("'")
                    index += 1
                else:
                    in_quote = False
            else:
                buffer.append(char)
        elif char == "'":
            in_quote = True
            quoted_value = True
        elif char == ",":
            value = "".join(buffer).strip()
            values.append(value if quoted_value or value.lower() != "null" else None)
            buffer = []
            quoted_value = False
        else:
            buffer.append(char)
        index += 1

    if in_quote:
        raise ValueError("unterminated SQL string")
    value = "".join(buffer).strip()
    values.append(value if quoted_value or value.lower() != "null" else None)
    return values


def iter_teacher_rows(
    path: Path, table_name: str, columns: tuple[str, ...]
) -> Iterator[dict[str, str | None]]:
    sql = path.read_text(encoding="utf-8")
    table_pattern = re.compile(
        rf"\bINSERT\s+INTO\s+(?:`?\w+`?\.)?`?{re.escape(table_name)}`?\b",
        flags=re.IGNORECASE,
    )
    for statement in _split_sql_statements(sql):
        if not table_pattern.search(statement):
            continue
        values = _parse_values(statement)
        if len(values) != len(columns):
            raise ValueError(
                f"{table_name} row has {len(values)} values, expected {len(columns)}"
            )
        yield dict(zip(columns, values, strict=True))


def _nullable_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_datetime(value: str | None) -> datetime | None:
    value = _nullable_text(value)
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _parse_decimal(value: str | None) -> Decimal | None:
    value = _nullable_text(value)
    return Decimal(value) if value is not None else None


def _parse_json_list(value: str | None) -> list[str]:
    value = _nullable_text(value)
    if value is None:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) for item in parsed
    ):
        raise ValueError("expected a JSON array of strings")
    return parsed


def _vulnerability_payload(row: dict[str, str | None]) -> VulnerabilityCreate:
    severity_value = (_nullable_text(row["severity"]) or Severity.UNKNOWN).upper()
    return VulnerabilityCreate(
        cve_id=row["cve_id"] or "",
        source_id=_nullable_text(row["source_id"]),
        source_name=_nullable_text(row["source_name"]),
        source_publish_date=_parse_datetime(row["source_publish_date"]),
        source_update_date=_parse_datetime(row["source_update_date"]),
        source_link=_nullable_text(row["source_link"]),
        affected_versions=_parse_json_list(row["affected_version"]),
        cvss_score_v4=_parse_decimal(row["cvss_score_v4"]),
        cvss_score_v3=_parse_decimal(row["cvss_score_v3"]),
        cvss_score_v2=_parse_decimal(row["cvss_score_v2"]),
        severity=Severity(severity_value),
        vulnerability_type=_nullable_text(row["type"]),
        cwe_ids=_parse_json_list(row["cwe_id"]),
        description=_nullable_text(row["description"]),
        title=_nullable_text(row["title"]),
    )


def _component_payload(row: dict[str, str | None]) -> ComponentCreate:
    return ComponentCreate(
        purl=row["purl"] or "",
        cpe=_nullable_text(row["cpe"]),
        ecosystem=_nullable_text(row["type"]),
        vendor=_nullable_text(row["vendor"]),
        name=row["name"] or "",
        version=_nullable_text(row["version"]),
        license=_nullable_text(row["license"]),
        description=_nullable_text(row["description"]),
        repository=_nullable_text(row["repository"]),
        publish_date=_parse_datetime(row["publish_date"]),
        language=_nullable_text(row["language"]),
        source_record_time=_parse_datetime(row["record_time"]),
    )


def _apply_changes(target: Any, values: dict[str, Any]) -> bool:
    changed = False
    for key, value in values.items():
        if getattr(target, key) != value:
            setattr(target, key, value)
            changed = True
    if changed:
        target.updated_at = get_datetime_utc()
    return changed


def import_vulnerabilities(session: Session, path: Path) -> ImportReport:
    report = ImportReport(source=str(path))
    for row_number, row in enumerate(
        iter_teacher_rows(path, "tmp_vul", VULNERABILITY_COLUMNS), start=1
    ):
        report.total += 1
        try:
            payload = _vulnerability_payload(row)
            existing = session.exec(
                select(Vulnerability).where(Vulnerability.cve_id == payload.cve_id)
            ).first()
            values = payload.model_dump()
            if existing is None:
                session.add(Vulnerability.model_validate(payload))
                report.inserted += 1
            elif _apply_changes(existing, values):
                session.add(existing)
                report.updated += 1
            else:
                report.unchanged += 1
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            report.add_error(row_number, error)
    return report


def import_components(session: Session, path: Path) -> ImportReport:
    report = ImportReport(source=str(path))
    for row_number, row in enumerate(
        iter_teacher_rows(path, "tmp_comp", COMPONENT_COLUMNS), start=1
    ):
        report.total += 1
        try:
            payload = _component_payload(row)
            existing = session.exec(
                select(Component).where(Component.purl == payload.purl)
            ).first()
            values = payload.model_dump()
            if existing is None:
                session.add(Component.model_validate(payload))
                report.inserted += 1
            elif _apply_changes(existing, values):
                session.add(existing)
                report.updated += 1
            else:
                report.unchanged += 1
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            report.add_error(row_number, error)
    return report
