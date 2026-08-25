"""008 expressms_mode on policies

Revision ID: 008
Revises: 007
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("expressms_mode", sa.String(length=16), nullable=False, server_default="otp"),
    )
    op.alter_column("policies", "expressms_mode", server_default=None)


def downgrade() -> None:
    op.drop_column("policies", "expressms_mode")
