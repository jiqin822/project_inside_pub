"""Add card_snapshot to activity_invites and planned_activities.

Revision ID: 022_card_snapshot
Revises: 021_scrapbook_layout
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "022_card_snapshot"
down_revision = "021_scrapbook_layout"
branch_labels = None
depends_on = None


def _column_exists(conn: sa.engine.Connection, table: str, column: str) -> bool:
    return column in [c["name"] for c in inspect(conn).get_columns(table)]


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "activity_invites", "card_snapshot"):
        op.add_column(
            "activity_invites",
            sa.Column("card_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )
    if not _column_exists(conn, "planned_activities", "card_snapshot"):
        op.add_column(
            "planned_activities",
            sa.Column("card_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, "planned_activities", "card_snapshot"):
        op.drop_column("planned_activities", "card_snapshot")
    if _column_exists(conn, "activity_invites", "card_snapshot"):
        op.drop_column("activity_invites", "card_snapshot")
