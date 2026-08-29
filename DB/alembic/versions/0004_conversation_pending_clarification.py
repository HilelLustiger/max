"""add pending_clarification to conversations

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("pending_clarification", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "pending_clarification")
