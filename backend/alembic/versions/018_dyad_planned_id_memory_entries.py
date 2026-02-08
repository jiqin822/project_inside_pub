"""Add planned_id and memory_entries to dyad_activity_history.

Revision ID: 018_dyad_planned_memory
Revises: 017_user_description_hobbies
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "018_dyad_planned_memory"
down_revision = "017_user_description_hobbies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dyad_activity_history",
        sa.Column("planned_id", sa.String(), nullable=True),
    )
    op.add_column(
        "dyad_activity_history",
        sa.Column("memory_entries", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "ix_dyad_activity_history_planned_id",
        "dyad_activity_history",
        ["planned_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dyad_activity_history_planned_id", table_name="dyad_activity_history")
    op.drop_column("dyad_activity_history", "memory_entries")
    op.drop_column("dyad_activity_history", "planned_id")
