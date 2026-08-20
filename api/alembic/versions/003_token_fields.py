"""Token serial, active flag, last_used on users.

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("token_serial", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("token_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("token_description", sa.String(length=256), nullable=True))
    op.create_index("ix_users_token_serial", "users", ["token_serial"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_token_serial", table_name="users")
    op.drop_column("users", "token_description")
    op.drop_column("users", "last_used_at")
    op.drop_column("users", "token_active")
    op.drop_column("users", "token_serial")
