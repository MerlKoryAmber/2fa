"""Enrollment invites, ldap_email, invite TTL policy.

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ldap_email", sa.String(length=256), nullable=True))
    op.add_column(
        "policies",
        sa.Column("enroll_invite_ttl_seconds", sa.Integer(), nullable=False, server_default="86400"),
    )
    op.create_table(
        "enrollment_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("email_to", sa.String(length=256), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_enrollment_invites_token", "enrollment_invites", ["token"], unique=True)
    op.create_index("ix_enrollment_invites_user_id", "enrollment_invites", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_enrollment_invites_user_id", table_name="enrollment_invites")
    op.drop_index("ix_enrollment_invites_token", table_name="enrollment_invites")
    op.drop_table("enrollment_invites")
    op.drop_column("policies", "enroll_invite_ttl_seconds")
    op.drop_column("users", "ldap_email")
