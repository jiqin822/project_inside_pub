"""Add birthday and occupation to users (optional personal profile fields).

Revision ID: 036_user_birthday_occupation
Revises: 035_kai_prefs_text
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa

revision = "036_user_birthday_occupation"
down_revision = "035_kai_prefs_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("occupation", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "occupation")
    op.drop_column("users", "birthday")
