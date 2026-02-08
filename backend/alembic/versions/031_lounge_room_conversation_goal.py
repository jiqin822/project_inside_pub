"""Add conversation_goal to lounge_rooms.

Revision ID: 031_lounge_goal
Revises: 030_things_to_find_out
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "031_lounge_goal"
down_revision = "030_things_to_find_out"
branch_labels = None
depends_on = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :t AND column_name = :c LIMIT 1"
        ),
        {"t": table_name, "c": column_name},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, "lounge_rooms", "conversation_goal"):
        return
    op.add_column(
        "lounge_rooms",
        sa.Column("conversation_goal", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lounge_rooms", "conversation_goal")
