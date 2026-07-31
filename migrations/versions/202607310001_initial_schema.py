"""initial schema

Revision ID: 202607310001
Revises:
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607310001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    return any(index["name"] == index_name for index in indexes)


def upgrade() -> None:
    if not _has_table("assets"):
        op.create_table(
            "assets",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("asset_type", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("storage_url", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("assets", "ix_assets_user_id"):
        op.create_index("ix_assets_user_id", "assets", ["user_id"], unique=False)

    if not _has_table("composition_jobs"):
        op.create_table(
            "composition_jobs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("stage", sa.String(), nullable=True),
            sa.Column("gif_url", sa.String(), nullable=True),
            sa.Column("source_gif_url", sa.String(), nullable=True),
            sa.Column("target_url", sa.String(), nullable=True),
            sa.Column("source_gif_asset_id", sa.String(), nullable=True),
            sa.Column("target_asset_id", sa.String(), nullable=True),
            sa.Column("draft_asset_id", sa.String(), nullable=True),
            sa.Column("result_asset_id", sa.String(), nullable=True),
            sa.Column("result_url", sa.String(), nullable=True),
            sa.Column("failed_reason", sa.String(), nullable=True),
            sa.Column("durations_ms", sa.JSON(), nullable=True),
            sa.Column("spec", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("composition_jobs", "ix_composition_jobs_user_id"):
        op.create_index(
            "ix_composition_jobs_user_id",
            "composition_jobs",
            ["user_id"],
            unique=False,
        )

    if not _has_table("credit_accounts"):
        op.create_table(
            "credit_accounts",
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("balance", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("provider", sa.String(), nullable=False),
            sa.Column("provider_id", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("role", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _has_index("users", "ix_users_provider_id"):
        op.create_index("ix_users_provider_id", "users", ["provider_id"], unique=False)

    if not _has_table("credit_transactions"):
        op.create_table(
            "credit_transactions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("account_user_id", sa.String(), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("transaction_type", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["account_user_id"], ["credit_accounts.user_id"]),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    op.drop_table("credit_transactions")
    op.drop_index(op.f("ix_users_provider_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("credit_accounts")
    op.drop_index(op.f("ix_composition_jobs_user_id"), table_name="composition_jobs")
    op.drop_table("composition_jobs")
    op.drop_index(op.f("ix_assets_user_id"), table_name="assets")
    op.drop_table("assets")
