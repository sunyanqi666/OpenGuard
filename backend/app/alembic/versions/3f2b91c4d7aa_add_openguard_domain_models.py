"""Add OpenGuard vulnerability and component domain models.

Revision ID: 3f2b91c4d7aa
Revises: fe56fa70289e
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "3f2b91c4d7aa"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vulnerability",
        sa.Column("cve_id", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("source_name", sa.String(length=32), nullable=True),
        sa.Column("source_publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_update_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_link", sa.String(length=2048), nullable=True),
        sa.Column(
            "affected_versions",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column("cvss_score_v4", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("cvss_score_v3", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("cvss_score_v2", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("vulnerability_type", sa.String(length=255), nullable=True),
        sa.Column(
            "cwe_ids",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cve_id ~ '^CVE-[0-9]{4}-[0-9]{4,}$'",
            name="ck_vulnerability_cve_id_format",
        ),
        sa.CheckConstraint(
            "cvss_score_v4 IS NULL OR cvss_score_v4 BETWEEN 0 AND 10",
            name="ck_vulnerability_cvss_v4_range",
        ),
        sa.CheckConstraint(
            "cvss_score_v3 IS NULL OR cvss_score_v3 BETWEEN 0 AND 10",
            name="ck_vulnerability_cvss_v3_range",
        ),
        sa.CheckConstraint(
            "cvss_score_v2 IS NULL OR cvss_score_v2 BETWEEN 0 AND 10",
            name="ck_vulnerability_cvss_v2_range",
        ),
        sa.CheckConstraint(
            "severity IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN')",
            name="ck_vulnerability_severity",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vulnerability_cve_id", "vulnerability", ["cve_id"], unique=True)
    op.create_index("ix_vulnerability_severity", "vulnerability", ["severity"])
    op.create_index("ix_vulnerability_source_name", "vulnerability", ["source_name"])

    op.create_table(
        "component",
        sa.Column("purl", sa.String(length=1024), nullable=False),
        sa.Column("cpe", sa.String(length=1024), nullable=True),
        sa.Column("ecosystem", sa.String(length=64), nullable=True),
        sa.Column("vendor", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=255), nullable=True),
        sa.Column("license", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("repository", sa.String(length=2048), nullable=True),
        sa.Column("publish_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("language", sa.String(length=64), nullable=True),
        sa.Column("source_record_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("purl LIKE 'pkg:%/%'", name="ck_component_purl_format"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_component_name_not_blank"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_component_cpe", "component", ["cpe"])
    op.create_index("ix_component_ecosystem", "component", ["ecosystem"])
    op.create_index("ix_component_language", "component", ["language"])
    op.create_index("ix_component_name", "component", ["name"])
    op.create_index("ix_component_purl", "component", ["purl"], unique=True)
    op.create_index("ix_component_vendor", "component", ["vendor"])

    op.create_table(
        "vulnerability_component",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vulnerability_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("match_method", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmed_by_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence BETWEEN 0 AND 1",
            name="ck_vulnerability_component_confidence",
        ),
        sa.CheckConstraint(
            "status IN ('SUGGESTED', 'CONFIRMED', 'REJECTED')",
            name="ck_vulnerability_component_status",
        ),
        sa.CheckConstraint(
            "match_method IN ('MANUAL', 'CPE', 'NAME', 'IMPORT')",
            name="ck_vulnerability_component_match_method",
        ),
        sa.ForeignKeyConstraint(["component_id"], ["component.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["vulnerability_id"], ["vulnerability.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vulnerability_id", "component_id", name="uq_vulnerability_component_pair"
        ),
    )
    op.create_index(
        "ix_vulnerability_component_component_id",
        "vulnerability_component",
        ["component_id"],
    )
    op.create_index(
        "ix_vulnerability_component_status", "vulnerability_component", ["status"]
    )
    op.create_index(
        "ix_vulnerability_component_vulnerability_id",
        "vulnerability_component",
        ["vulnerability_id"],
    )

    op.create_table(
        "remediation",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vulnerability_id", sa.Uuid(), nullable=False),
        sa.Column("component_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("fixed_version", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'IN_PROGRESS', 'FIXED', 'IGNORED')",
            name="ck_remediation_status",
        ),
        sa.ForeignKeyConstraint(["assignee_id"], ["user.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["component_id"], ["component.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["vulnerability_id"], ["vulnerability.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_remediation_assignee_id", "remediation", ["assignee_id"])
    op.create_index("ix_remediation_component_id", "remediation", ["component_id"])
    op.create_index("ix_remediation_status", "remediation", ["status"])
    op.create_index(
        "ix_remediation_vulnerability_id", "remediation", ["vulnerability_id"]
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=True),
        sa.Column(
            "changes",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('CREATE', 'UPDATE', 'DELETE', 'LINK', 'UNLINK', "
            "'STATUS_CHANGE')",
            name="ck_audit_log_action",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_resource_id", "audit_log", ["resource_id"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_resource_type", table_name="audit_log")
    op.drop_index("ix_audit_log_resource_id", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_actor_id", table_name="audit_log")
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_remediation_vulnerability_id", table_name="remediation")
    op.drop_index("ix_remediation_status", table_name="remediation")
    op.drop_index("ix_remediation_component_id", table_name="remediation")
    op.drop_index("ix_remediation_assignee_id", table_name="remediation")
    op.drop_table("remediation")

    op.drop_index(
        "ix_vulnerability_component_vulnerability_id",
        table_name="vulnerability_component",
    )
    op.drop_index(
        "ix_vulnerability_component_status", table_name="vulnerability_component"
    )
    op.drop_index(
        "ix_vulnerability_component_component_id",
        table_name="vulnerability_component",
    )
    op.drop_table("vulnerability_component")

    op.drop_index("ix_component_vendor", table_name="component")
    op.drop_index("ix_component_purl", table_name="component")
    op.drop_index("ix_component_name", table_name="component")
    op.drop_index("ix_component_language", table_name="component")
    op.drop_index("ix_component_ecosystem", table_name="component")
    op.drop_index("ix_component_cpe", table_name="component")
    op.drop_table("component")

    op.drop_index("ix_vulnerability_source_name", table_name="vulnerability")
    op.drop_index("ix_vulnerability_severity", table_name="vulnerability")
    op.drop_index("ix_vulnerability_cve_id", table_name="vulnerability")
    op.drop_table("vulnerability")
