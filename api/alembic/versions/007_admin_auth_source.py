"""Admin auth_source for local vs AD panel login.

Revision ID: 007
Revises: 006
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admins",
        sa.Column("auth_source", sa.String(length=16), nullable=False, server_default="local"),
    )
    op.alter_column("admins", "auth_source", server_default=None)
    op.alter_column("admins", "password_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade() -> None:
    op.execute("UPDATE admins SET password_hash = '' WHERE password_hash IS NULL")
    op.alter_column("admins", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_column("admins", "auth_source")
