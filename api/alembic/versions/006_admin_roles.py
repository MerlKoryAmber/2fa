"""Admin roles and is_active.

Revision ID: 006
Revises: 005
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="admin"),
    )
    op.add_column(
        "admins",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("admins", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("admins", "role", server_default=None)
    op.alter_column("admins", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("admins", "updated_at")
    op.drop_column("admins", "is_active")
    op.drop_column("admins", "role")
