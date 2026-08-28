"""goals, tasks, habits, habit_logs

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-28

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("active", "completed", "archived", name="goal_status", native_enum=False),
            server_default="active",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("goal_id", sa.String(), sa.ForeignKey("goals.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "not_started", "in_progress", "done", name="task_status", native_enum=False
            ),
            server_default="not_started",
            nullable=False,
        ),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "habits",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("goal_id", sa.String(), sa.ForeignKey("goals.id"), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(), server_default="daily", nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="habit_status", native_enum=False),
            server_default="active",
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "habit_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("habit_id", sa.String(), sa.ForeignKey("habits.id"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("habit_logs")
    op.drop_table("habits")
    op.drop_table("tasks")
    op.drop_table("goals")
