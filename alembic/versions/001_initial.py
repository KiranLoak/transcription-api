"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("rate_limit_rpm", sa.Integer(), server_default="30"),
        sa.Column("monthly_job_quota", sa.Integer(), server_default="500"),
        sa.Column("jobs_used_this_month", sa.Integer(), server_default="0"),
        sa.Column("quota_reset_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)

    op.create_table(
        "transcription_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("input_url", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("original_filename", sa.String(512)),
        sa.Column("webhook_url", sa.Text()),
        sa.Column("result", postgresql.JSON(astext_type=sa.Text())),
        sa.Column("error", postgresql.JSON(astext_type=sa.Text())),
        sa.Column("pipeline_cost_usd", sa.Float()),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_transcription_jobs_status", "transcription_jobs", ["status"])

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id")),
        sa.Column("job_id", postgresql.UUID(as_uuid=True)),
        sa.Column("provider", sa.String(64)),
        sa.Column("model", sa.String(128)),
        sa.Column("cost_usd", sa.Float()),
        sa.Column("billed_units", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("usage_records")
    op.drop_table("transcription_jobs")
    op.drop_table("api_keys")
