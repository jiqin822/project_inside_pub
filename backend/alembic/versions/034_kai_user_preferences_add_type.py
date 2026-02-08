"""Add type column to kai_user_preferences if missing (legacy NOT NULL column).

Some DBs have a NOT NULL "type" column; the model now sets it. This migration
ensures the column exists and is backfilled from kind so INSERTs succeed.
Revision ID: 034_kai_prefs_type
Revises: 033_kai_prefs_missing
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "034_kai_prefs_type"
down_revision = "033_kai_prefs_missing"
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
    if _column_exists(conn, t, "type"):
        return
    op.add_column(t, sa.Column("type", sa.String(), nullable=True, index=True))
    op.execute("UPDATE kai_user_preferences SET type = COALESCE(kind, 'preference') WHERE type IS NULL")
    op.alter_column(t, "type", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    conn = op.get_bind()
    t = "kai_user_preferences"
    if _column_exists(conn, t, "type"):
        op.drop_column(t, "type")
