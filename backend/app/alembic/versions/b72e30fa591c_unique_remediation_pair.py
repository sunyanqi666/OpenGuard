"""Ensure one remediation per vulnerability and component pair.

Revision ID: b72e30fa591c
Revises: 8a41d62c5e18
Create Date: 2026-09-21
"""

from alembic import op

revision = "b72e30fa591c"
down_revision = "8a41d62c5e18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_remediation_vulnerability_component",
        "remediation",
        ["vulnerability_id", "component_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_remediation_vulnerability_component", "remediation", type_="unique"
    )
