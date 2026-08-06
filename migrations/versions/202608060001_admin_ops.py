"""admin ops support

Revision ID: 202608060001
Revises: 202608050002
Create Date: 2026-08-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202608060001"
down_revision: Union[str, None] = "202608050002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if _has_table("credit_transactions") and not _has_column("credit_transactions", "reason"):
        op.add_column("credit_transactions", sa.Column("reason", sa.String(), nullable=True))

    if not _has_table("admin_audit_logs"):
        op.create_table(
            "admin_audit_logs",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("admin_user_id", sa.String(), nullable=False),
            sa.Column("action", sa.String(), nullable=False),
            sa.Column("target_type", sa.String(), nullable=False),
            sa.Column("target_id", sa.String(), nullable=False),
            sa.Column("reason", sa.String(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("idempotency_key", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if _has_table("admin_audit_logs") and not _has_index("admin_audit_logs", "ix_admin_audit_logs_admin_user_id"):
        op.create_index(
            "ix_admin_audit_logs_admin_user_id",
            "admin_audit_logs",
            ["admin_user_id"],
            unique=False,
        )
    if _has_table("admin_audit_logs") and not _has_column("admin_audit_logs", "idempotency_key"):
        op.add_column("admin_audit_logs", sa.Column("idempotency_key", sa.String(), nullable=True))
    if _has_table("admin_audit_logs") and not _has_index("admin_audit_logs", "uq_admin_audit_logs_idempotency_key"):
        op.create_index(
            "uq_admin_audit_logs_idempotency_key",
            "admin_audit_logs",
            ["idempotency_key"],
            unique=True,
        )


def downgrade() -> None:
    if _has_table("admin_audit_logs"):
        if _has_index("admin_audit_logs", "uq_admin_audit_logs_idempotency_key"):
            op.drop_index("uq_admin_audit_logs_idempotency_key", table_name="admin_audit_logs")
        if _has_index("admin_audit_logs", "ix_admin_audit_logs_admin_user_id"):
            op.drop_index("ix_admin_audit_logs_admin_user_id", table_name="admin_audit_logs")
        op.drop_table("admin_audit_logs")
    if _has_table("credit_transactions") and _has_column("credit_transactions", "reason"):
        op.drop_column("credit_transactions", "reason")
