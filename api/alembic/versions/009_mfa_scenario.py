"""009 mfa_scenario + push_wait_seconds on policies

Revision ID: 009
Revises: 008
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("mfa_scenario", sa.String(length=32), nullable=False, server_default="totp"),
    )
    op.add_column(
        "policies",
        sa.Column("push_wait_seconds", sa.Integer(), nullable=False, server_default="60"),
    )
    # expressms_mode=push → express_push; иначе totp (безопасный дефолт для VPN)
    op.execute(
        "UPDATE policies SET mfa_scenario = 'express_push' WHERE lower(expressms_mode) = 'push'"
    )
    op.alter_column("policies", "mfa_scenario", server_default=None)
    op.alter_column("policies", "push_wait_seconds", server_default=None)


def downgrade() -> None:
    op.drop_column("policies", "push_wait_seconds")
    op.drop_column("policies", "mfa_scenario")
