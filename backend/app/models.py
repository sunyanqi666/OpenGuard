import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from pydantic import EmailStr, field_validator
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    SECURITY = "SECURITY"
    VIEWER = "VIEWER"


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    role: UserRole = Field(default=UserRole.VIEWER, sa_type=String(16))  # type: ignore
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    role: UserRole | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


# OpenGuard domain enumerations
class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AssociationStatus(StrEnum):
    SUGGESTED = "SUGGESTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class MatchMethod(StrEnum):
    MANUAL = "MANUAL"
    CPE = "CPE"
    NAME = "NAME"
    IMPORT = "IMPORT"


class RemediationStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    FIXED = "FIXED"
    IGNORED = "IGNORED"


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    LINK = "LINK"
    UNLINK = "UNLINK"
    STATUS_CHANGE = "STATUS_CHANGE"


def validate_cve_id(value: str) -> str:
    normalized = value.strip().upper()
    parts = normalized.split("-")
    if (
        len(parts) != 3
        or parts[0] != "CVE"
        or len(parts[1]) != 4
        or not parts[1].isdigit()
        or len(parts[2]) < 4
        or not parts[2].isdigit()
    ):
        raise ValueError("CVE ID must use the format CVE-YYYY-NNNN")
    return normalized


class VulnerabilityBase(SQLModel):
    cve_id: str = Field(min_length=13, max_length=32)
    source_id: str | None = Field(default=None, max_length=64)
    source_name: str | None = Field(default=None, max_length=32, index=True)
    source_publish_date: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    source_update_date: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    source_link: str | None = Field(default=None, max_length=2048)
    affected_versions: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    cvss_score_v4: Decimal | None = Field(
        default=None,
        ge=0,
        le=10,
        sa_type=Numeric(3, 1),  # type: ignore
    )
    cvss_score_v3: Decimal | None = Field(
        default=None,
        ge=0,
        le=10,
        sa_type=Numeric(3, 1),  # type: ignore
    )
    cvss_score_v2: Decimal | None = Field(
        default=None,
        ge=0,
        le=10,
        sa_type=Numeric(3, 1),  # type: ignore
    )
    severity: Severity = Field(
        default=Severity.UNKNOWN,
        sa_column=Column(String(16), nullable=False, index=True),
    )
    vulnerability_type: str | None = Field(default=None, max_length=255)
    cwe_ids: list[str] = Field(
        default_factory=list, sa_column=Column(JSON, nullable=False)
    )
    description: str | None = Field(default=None, sa_column=Column(Text))
    title: str | None = Field(default=None, max_length=512)

    @field_validator("cve_id")
    @classmethod
    def normalize_cve_id(cls, value: str) -> str:
        return validate_cve_id(value)


class Vulnerability(VulnerabilityBase, table=True):
    __tablename__ = "vulnerability"
    __table_args__ = (
        CheckConstraint(
            "cve_id ~ '^CVE-[0-9]{4}-[0-9]{4,}$'",
            name="ck_vulnerability_cve_id_format",
        ),
        CheckConstraint(
            "cvss_score_v4 IS NULL OR cvss_score_v4 BETWEEN 0 AND 10",
            name="ck_vulnerability_cvss_v4_range",
        ),
        CheckConstraint(
            "cvss_score_v3 IS NULL OR cvss_score_v3 BETWEEN 0 AND 10",
            name="ck_vulnerability_cvss_v3_range",
        ),
        CheckConstraint(
            "cvss_score_v2 IS NULL OR cvss_score_v2 BETWEEN 0 AND 10",
            name="ck_vulnerability_cvss_v2_range",
        ),
        CheckConstraint(
            "severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')",
            name="ck_vulnerability_severity",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    cve_id: str = Field(min_length=13, max_length=32, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class VulnerabilityCreate(VulnerabilityBase):
    """Used by trusted import and optional administrator creation workflows."""


class VulnerabilityUpdate(SQLModel):
    cve_id: None = None
    source_name: str | None = Field(default=None, max_length=32)
    source_publish_date: datetime | None = None
    source_update_date: datetime | None = None
    source_link: str | None = Field(default=None, max_length=2048)
    affected_versions: list[str] | None = None
    cvss_score_v4: Decimal | None = Field(default=None, ge=0, le=10)
    cvss_score_v3: Decimal | None = Field(default=None, ge=0, le=10)
    cvss_score_v2: Decimal | None = Field(default=None, ge=0, le=10)
    severity: Severity | None = None
    vulnerability_type: str | None = Field(default=None, max_length=255)
    cwe_ids: list[str] | None = None
    description: str | None = None
    title: str | None = Field(default=None, max_length=512)


class VulnerabilityPublic(VulnerabilityBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class VulnerabilitiesPublic(SQLModel):
    data: list[VulnerabilityPublic]
    count: int


def validate_component_purl(value: str) -> str:
    normalized = value.strip()
    if not normalized.startswith("pkg:") or "/" not in normalized:
        raise ValueError("PURL must start with 'pkg:' and contain a package path")
    return normalized


def validate_component_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("Component name must not be blank")
    return normalized


def validate_repository_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Repository must be an HTTP or HTTPS URL")
    return normalized


class ComponentBase(SQLModel):
    purl: str = Field(min_length=5, max_length=1024)
    cpe: str | None = Field(default=None, max_length=1024, index=True)
    ecosystem: str | None = Field(default=None, max_length=64, index=True)
    vendor: str | None = Field(default=None, max_length=255, index=True)
    name: str = Field(min_length=1, max_length=255, index=True)
    version: str | None = Field(default=None, max_length=255)
    license: str | None = Field(default=None, sa_column=Column(Text))
    description: str | None = Field(default=None, sa_column=Column(Text))
    repository: str | None = Field(default=None, max_length=2048)
    publish_date: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    language: str | None = Field(default=None, max_length=64, index=True)
    source_record_time: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore
    )

    @field_validator("purl")
    @classmethod
    def validate_purl(cls, value: str) -> str:
        return validate_component_purl(value)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return validate_component_name(value)

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str | None) -> str | None:
        return validate_repository_url(value)


class Component(ComponentBase, table=True):
    __tablename__ = "component"
    __table_args__ = (
        CheckConstraint("purl LIKE 'pkg:%/%'", name="ck_component_purl_format"),
        CheckConstraint("length(trim(name)) > 0", name="ck_component_name_not_blank"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    purl: str = Field(min_length=5, max_length=1024, unique=True, index=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class ComponentCreate(ComponentBase):
    pass


class ComponentUpdate(SQLModel):
    purl: str | None = Field(default=None, min_length=5, max_length=1024)
    cpe: str | None = Field(default=None, max_length=1024)
    ecosystem: str | None = Field(default=None, max_length=64)
    vendor: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    version: str | None = Field(default=None, max_length=255)
    license: str | None = None
    description: str | None = None
    repository: str | None = Field(default=None, max_length=2048)
    publish_date: datetime | None = None
    language: str | None = Field(default=None, max_length=64)

    @field_validator("purl")
    @classmethod
    def validate_optional_purl(cls, value: str | None) -> str | None:
        return validate_component_purl(value) if value is not None else None

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        return validate_component_name(value) if value is not None else None

    @field_validator("repository")
    @classmethod
    def validate_optional_repository(cls, value: str | None) -> str | None:
        return validate_repository_url(value)


class ComponentPublic(ComponentBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ComponentsPublic(SQLModel):
    data: list[ComponentPublic]
    count: int


class VulnerabilityComponent(SQLModel, table=True):
    __tablename__ = "vulnerability_component"
    __table_args__ = (
        UniqueConstraint(
            "vulnerability_id", "component_id", name="uq_vulnerability_component_pair"
        ),
        CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_vulnerability_component_confidence",
        ),
        CheckConstraint(
            "status IN ('SUGGESTED', 'CONFIRMED', 'REJECTED')",
            name="ck_vulnerability_component_status",
        ),
        CheckConstraint(
            "match_method IN ('MANUAL', 'CPE', 'NAME', 'IMPORT')",
            name="ck_vulnerability_component_match_method",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vulnerability_id: uuid.UUID = Field(
        foreign_key="vulnerability.id", nullable=False, ondelete="CASCADE", index=True
    )
    component_id: uuid.UUID = Field(
        foreign_key="component.id", nullable=False, ondelete="CASCADE", index=True
    )
    status: AssociationStatus = Field(
        default=AssociationStatus.SUGGESTED,
        sa_type=String(16),  # type: ignore
        index=True,
    )
    match_method: MatchMethod = Field(
        default=MatchMethod.MANUAL,
        sa_type=String(16),  # type: ignore
    )
    confidence: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
        sa_type=Numeric(4, 3),  # type: ignore
    )
    notes: str | None = Field(default=None, sa_column=Column(Text))
    affected_version_range: str | None = Field(default=None, max_length=512)
    source_reference: str | None = Field(default=None, max_length=2048)
    confirmed_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL"
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class VulnerabilityComponentCreate(SQLModel):
    vulnerability_id: uuid.UUID
    component_id: uuid.UUID
    affected_version_range: str | None = Field(default=None, max_length=512)
    source_reference: str | None = Field(default=None, max_length=2048)
    notes: str | None = None
    match_method: MatchMethod = MatchMethod.MANUAL


class VulnerabilityComponentPublic(SQLModel):
    id: uuid.UUID
    vulnerability_id: uuid.UUID
    component_id: uuid.UUID
    status: AssociationStatus
    match_method: MatchMethod
    confidence: Decimal | None
    affected_version_range: str | None
    source_reference: str | None
    notes: str | None
    confirmed_by_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    cve_id: str
    severity: Severity
    component_name: str
    component_purl: str


class VulnerabilityComponentsPublic(SQLModel):
    data: list[VulnerabilityComponentPublic]
    count: int


class AssociationSuggestion(SQLModel):
    component: ComponentPublic
    match_method: MatchMethod
    confidence: Decimal
    reason: str


class Remediation(SQLModel, table=True):
    __tablename__ = "remediation"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'IN_PROGRESS', 'FIXED', 'IGNORED')",
            name="ck_remediation_status",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    vulnerability_id: uuid.UUID = Field(
        foreign_key="vulnerability.id", nullable=False, ondelete="CASCADE", index=True
    )
    component_id: uuid.UUID | None = Field(
        default=None, foreign_key="component.id", ondelete="CASCADE", index=True
    )
    status: RemediationStatus = Field(
        default=RemediationStatus.PENDING,
        sa_type=String(24),  # type: ignore
        index=True,
    )
    assignee_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    notes: str | None = Field(default=None, sa_column=Column(Text))
    due_date: date | None = None
    fixed_version: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )


class RemediationCreate(SQLModel):
    vulnerability_id: uuid.UUID
    component_id: uuid.UUID
    status: RemediationStatus = RemediationStatus.PENDING
    assignee_id: uuid.UUID | None = None
    notes: str | None = None
    due_date: date | None = None
    fixed_version: str | None = Field(default=None, max_length=255)


class RemediationUpdate(SQLModel):
    status: RemediationStatus | None = None
    assignee_id: uuid.UUID | None = None
    notes: str | None = None
    due_date: date | None = None
    fixed_version: str | None = Field(default=None, max_length=255)


class RemediationPublic(SQLModel):
    id: uuid.UUID
    vulnerability_id: uuid.UUID
    component_id: uuid.UUID | None
    status: RemediationStatus
    assignee_id: uuid.UUID | None
    assignee_name: str | None = None
    notes: str | None
    due_date: date | None
    fixed_version: str | None
    created_at: datetime
    updated_at: datetime
    cve_id: str
    component_name: str | None
    component_purl: str | None = None
    vulnerability_severity: Severity | None = None


class RemediationsPublic(SQLModel):
    data: list[RemediationPublic]
    count: int


class RemediationSummary(SQLModel):
    total: int
    pending: int
    in_progress: int
    fixed: int
    ignored: int
    overdue: int
    due_soon: int
    completed_this_month: int
    completion_rate: float


class DashboardBucket(SQLModel):
    label: str
    count: int


class DashboardRiskComponent(SQLModel):
    component_id: uuid.UUID
    name: str
    purl: str
    critical_count: int
    high_count: int
    total_count: int


class DashboardSummary(SQLModel):
    vulnerability_count: int
    component_count: int
    association_count: int
    pending_risk_count: int
    severity_distribution: list[DashboardBucket]
    cvss_distribution: list[DashboardBucket]
    publication_trend: list[DashboardBucket]
    remediation_distribution: list[DashboardBucket]
    high_risk_components: list[DashboardRiskComponent]


class AuditLog(SQLModel, table=True):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('CREATE', 'UPDATE', 'DELETE', 'LINK', 'UNLINK', "
            "'STATUS_CHANGE')",
            name="ck_audit_log_action",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    actor_id: uuid.UUID | None = Field(
        default=None, foreign_key="user.id", ondelete="SET NULL", index=True
    )
    action: AuditAction = Field(sa_type=String(24), index=True)  # type: ignore
    resource_type: str = Field(min_length=1, max_length=64, index=True)
    resource_id: uuid.UUID = Field(index=True)
    summary: str | None = Field(default=None, max_length=512)
    changes: dict[str, Any] = Field(
        default_factory=dict, sa_column=Column(JSON, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
        index=True,
    )


class AuditLogPublic(SQLModel):
    id: uuid.UUID
    actor_id: uuid.UUID | None
    actor_email: str | None = None
    action: AuditAction
    resource_type: str
    resource_id: uuid.UUID
    summary: str | None
    changes: dict[str, Any]
    created_at: datetime


class AuditLogsPublic(SQLModel):
    data: list[AuditLogPublic]
    count: int


class ImportIssue(SQLModel):
    row: int
    message: str


class ComponentImportResult(SQLModel):
    created: int
    updated: int
    skipped: int
    failed: int
    issues: list[ImportIssue]
