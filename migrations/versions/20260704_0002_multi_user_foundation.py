"""Add users, knowledge bases, and document ownership.

Revision ID: 20260704_0002
Revises: 20260704_0001
Create Date: 2026-07-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260704_0002"
down_revision: str | Sequence[str] | None = "20260704_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"
LEGACY_KNOWLEDGE_BASE_ID = "00000000-0000-0000-0000-000000000002"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "knowledge_bases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_knowledge_bases_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_bases")),
    )
    op.create_index(
        op.f("ix_knowledge_bases_user_id"),
        "knowledge_bases",
        ["user_id"],
        unique=False,
    )

    op.add_column(
        "documents",
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    # Preserve rows created before tenant ownership existed. Fresh databases do
    # not receive these legacy records because the inserts are conditional.
    op.execute(
        f"""
        INSERT INTO users (id, email)
        SELECT '{LEGACY_USER_ID}'::uuid, 'legacy@local.invalid'
        WHERE EXISTS (SELECT 1 FROM documents)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO knowledge_bases (id, user_id, name, description)
        SELECT
            '{LEGACY_KNOWLEDGE_BASE_ID}'::uuid,
            '{LEGACY_USER_ID}'::uuid,
            'Legacy Documents',
            'Documents migrated before multi-user ownership was introduced.'
        WHERE EXISTS (SELECT 1 FROM documents)
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        f"""
        UPDATE documents
        SET knowledge_base_id = '{LEGACY_KNOWLEDGE_BASE_ID}'::uuid
        WHERE knowledge_base_id IS NULL
        """
    )

    op.alter_column("documents", "knowledge_base_id", nullable=False)
    op.create_foreign_key(
        op.f("fk_documents_knowledge_base_id_knowledge_bases"),
        "documents",
        "knowledge_bases",
        ["knowledge_base_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_documents_knowledge_base_id"),
        "documents",
        ["knowledge_base_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_documents_knowledge_base_id"),
        table_name="documents",
    )
    op.drop_constraint(
        op.f("fk_documents_knowledge_base_id_knowledge_bases"),
        "documents",
        type_="foreignkey",
    )
    op.drop_column("documents", "knowledge_base_id")
    op.drop_index(
        op.f("ix_knowledge_bases_user_id"),
        table_name="knowledge_bases",
    )
    op.drop_table("knowledge_bases")
    op.drop_table("users")
