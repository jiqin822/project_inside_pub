"""Add scrapbook_layout to planned_activities.

Revision ID: 021_scrapbook_layout
Revises: 020_devices_table
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "021_scrapbook_layout"
down_revision = "020_devices_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "planned_activities",
        sa.Column("scrapbook_layout", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("planned_activities", "scrapbook_layout")
