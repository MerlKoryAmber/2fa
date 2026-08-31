"""010 express_channel_enabled on users

Revision ID: 010
Revises: 009
Create Date: 2026-08-31
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("express_channel_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Уже привязанные через /start — оставить включёнными.
    op.execute(
        "UPDATE users SET express_channel_enabled = true "
        "WHERE expressms_id IS NOT NULL AND trim(expressms_id) <> ''"
    )
    op.alter_column("users", "express_channel_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "express_channel_enabled")
