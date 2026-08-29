"""add category to goals and habits

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("goals", sa.Column("category", sa.String(), nullable=True))
    op.add_column("habits", sa.Column("category", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("habits", "category")
    op.drop_column("goals", "category")
