"""Add association version range and source metadata.

Revision ID: 8a41d62c5e18
Revises: 3f2b91c4d7aa
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "8a41d62c5e18"
down_revision = "3f2b91c4d7aa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vulnerability_component",
        sa.Column("affected_version_range", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "vulnerability_component",
        sa.Column("source_reference", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vulnerability_component", "source_reference")
    op.drop_column("vulnerability_component", "affected_version_range")
