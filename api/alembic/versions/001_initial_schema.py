"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-08-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_admins_username", "admins", ["username"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ad_username", sa.String(length=256), nullable=False),
        sa.Column("otp_method", sa.String(length=32), nullable=False),
        sa.Column("expressms_id", sa.String(length=256), nullable=True),
        sa.Column("totp_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("totp_confirmed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_ad_username", "users", ["ad_username"], unique=True)

    op.create_table(
        "policies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("scope", sa.String(length=256), nullable=False),
        sa.Column("require_2fa", sa.Boolean(), nullable=False),
        sa.Column("allowed_second_factors", sa.String(length=128), nullable=False),
        sa.Column("totp_window_steps", sa.Integer(), nullable=False),
        sa.Column("otp_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("max_otp_attempts_per_challenge", sa.Integer(), nullable=False),
        sa.Column("challenge_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("radius_scheme_preference", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state_token", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("method_used", sa.String(length=32), nullable=False),
        sa.Column("otp_hash", sa.String(length=128), nullable=True),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts_count", sa.Integer(), nullable=False),
        sa.Column("consumed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_otp_challenges_state_token", "otp_challenges", ["state_token"], unique=True)
    op.create_index("ix_otp_challenges_user_id", "otp_challenges", ["user_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("username", sa.String(length=256), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("otp_challenges")
    op.drop_table("policies")
    op.drop_table("users")
    op.drop_table("admins")
