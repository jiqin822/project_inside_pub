"""Add text column to kai_user_preferences if missing (legacy NOT NULL column).

Some DBs have a NOT NULL "text" column; the model now sets it. This migration
ensures the column exists and is backfilled from content so INSERTs succeed.
Revision ID: 035_kai_prefs_text
Revises: 034_kai_prefs_type
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "035_kai_prefs_text"
down_revision = "034_kai_prefs_type"
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
    t = "kai_user_preferences"
    if _column_exists(conn, t, "text"):
        return
    op.add_column(t, sa.Column("text", sa.Text(), nullable=True))
    op.execute("UPDATE kai_user_preferences SET text = COALESCE(content, '') WHERE text IS NULL")
    op.alter_column(t, "text", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    conn = op.get_bind()
    t = "kai_user_preferences"
    if _column_exists(conn, t, "text"):
        op.drop_column(t, "text")
