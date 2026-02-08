"""Add content column to kai_user_preferences if missing.

The table may have been created without this column (e.g. idempotent skip in 027).
Revision ID: 032_kai_prefs_content
Revises: 031_lounge_goal
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "032_kai_prefs_content"
down_revision = "031_lounge_goal"
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
    if _column_exists(conn, "kai_user_preferences", "content"):
        return
    op.add_column(
        "kai_user_preferences",
        sa.Column("content", sa.Text(), nullable=True),
    )
    # Backfill existing rows so we can set NOT NULL.
    op.execute("UPDATE kai_user_preferences SET content = '' WHERE content IS NULL")
    op.alter_column(
        "kai_user_preferences",
        "content",
        existing_type=sa.Text(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("kai_user_preferences", "content")
