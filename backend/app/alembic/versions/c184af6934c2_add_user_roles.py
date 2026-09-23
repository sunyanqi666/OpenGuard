"""Add user roles.

Revision ID: c184af6934c2
Revises: b72e30fa591c
Create Date: 2026-09-21
"""

import sqlalchemy as sa
from alembic import op

revision = "c184af6934c2"
down_revision = "b72e30fa591c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("role", sa.String(length=16), server_default="VIEWER", nullable=False),
    )
    op.execute("UPDATE \"user\" SET role='ADMIN' WHERE is_superuser=true")
    op.create_check_constraint(
        "ck_user_role", "user", "role IN ('ADMIN', 'SECURITY', 'VIEWER')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_role", "user", type_="check")
    op.drop_column("user", "role")
