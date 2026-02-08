"""Allow lounge_messages.sender_user_id to be NULL (Kai/system messages).

Revision ID: 026_lounge_sender_null
Revises: 025_lounge
Create Date: 2026-02-01

"""
from alembic import op
import sqlalchemy as sa

revision = "026_lounge_sender_null"
down_revision = "025_lounge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "lounge_messages",
        "sender_user_id",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "lounge_messages",
        "sender_user_id",
        existing_type=sa.String(),
        nullable=False,
    )
