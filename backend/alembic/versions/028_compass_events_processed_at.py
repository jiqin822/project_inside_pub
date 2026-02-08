"""Add processed_at to compass_events for threshold-based consolidation.

Revision ID: 028_compass_processed_at
Revises: 027_kai_user_prefs
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa

revision = "028_compass_processed_at"
down_revision = "027_kai_user_prefs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "compass_events",
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_compass_events_actor_processed",
        "compass_events",
        ["actor_user_id", "processed_at"],
        unique=False,
    )
    op.create_index(
        "ix_compass_events_relationship_processed",
        "compass_events",
        ["relationship_id", "processed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_compass_events_relationship_processed", table_name="compass_events")
    op.drop_index("ix_compass_events_actor_processed", table_name="compass_events")
    op.drop_column("compass_events", "processed_at")
