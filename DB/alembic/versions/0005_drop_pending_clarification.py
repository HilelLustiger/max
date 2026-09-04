"""drop pending_clarification from conversations

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("conversations", "pending_clarification")


def downgrade() -> None:
    op.add_column("conversations", sa.Column("pending_clarification", JSONB(), nullable=True))
