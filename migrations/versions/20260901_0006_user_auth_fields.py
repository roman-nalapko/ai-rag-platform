"""Add hashed_password to users for password-based authentication.

Revision ID: 20260901_0006
Revises: 20260705_0005
Create Date: 2026-09-01

The column is nullable so existing demo-mode users (created without a
password via POST /users) remain valid. Password-based auth is opt-in.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0006"
down_revision: str | Sequence[str] | None = "20260705_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "hashed_password",
            sa.String(length=255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
