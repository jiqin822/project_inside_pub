"""Add devices table for push tokens.

Revision ID: 020_devices_table
Revises: 019_relationship_type_date
Create Date: 2026-01-30

"""
from alembic import op
import sqlalchemy as sa

revision = "020_devices_table"
down_revision = "019_relationship_type_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("push_token", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_devices_user_id", "devices", ["user_id"], unique=False)
    op.create_index("ix_devices_push_token", "devices", ["push_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_devices_push_token", table_name="devices")
    op.drop_index("ix_devices_user_id", table_name="devices")
    op.drop_table("devices")
