"""Add asynchronous document processing status.

Revision ID: 20260705_0004
Revises: 20260704_0003
Create Date: 2026-07-05
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260705_0004"
down_revision: str | Sequence[str] | None = "20260704_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("status", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.execute(
        "UPDATE documents "
        "SET status = CASE WHEN processed THEN 'indexed' ELSE 'pending' END"
    )
    op.alter_column(
        "documents",
        "status",
        existing_type=sa.String(length=20),
        nullable=False,
        server_default="pending",
    )
    op.create_check_constraint(
        op.f("ck_documents_status"),
        "documents",
        "status IN ('pending', 'processing', 'indexed', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_documents_status"),
        "documents",
        type_="check",
    )
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")
