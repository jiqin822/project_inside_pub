"""Add love map tables

Revision ID: 009_add_love_map_tables
Revises: 007_market_item_rel
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '009_add_love_map_tables'
down_revision = '007_market_item_rel'
branch_labels = None
depends_on = None


def upgrade():
    # Create map_prompts table
    op.create_table(
        'map_prompts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('difficulty_tier', sa.Integer(), nullable=False),
        sa.Column('question_template', sa.Text(), nullable=False),
        sa.Column('input_prompt', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_map_prompts_category', 'map_prompts', ['category'])
    op.create_index('ix_map_prompts_difficulty_tier', 'map_prompts', ['difficulty_tier'])

    # Create user_specs table
    op.create_table(
        'user_specs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('prompt_id', sa.String(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('last_updated', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['prompt_id'], ['map_prompts.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'prompt_id', name='idx_user_specs_user_prompt')
    )
    op.create_index('ix_user_specs_user_id', 'user_specs', ['user_id'])
    op.create_index('ix_user_specs_prompt_id', 'user_specs', ['prompt_id'])

    # Create relationship_map_progress table
    op.create_table(
        'relationship_map_progress',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('observer_id', sa.String(), nullable=False),
        sa.Column('subject_id', sa.String(), nullable=False),
        sa.Column('level_tier', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('current_xp', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stars', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['observer_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['subject_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('observer_id', 'subject_id', name='idx_map_progress_observer_subject')
    )
    op.create_index('ix_relationship_map_progress_observer_id', 'relationship_map_progress', ['observer_id'])
    op.create_index('ix_relationship_map_progress_subject_id', 'relationship_map_progress', ['subject_id'])


def downgrade():
    op.drop_index('ix_relationship_map_progress_subject_id', table_name='relationship_map_progress')
    op.drop_index('ix_relationship_map_progress_observer_id', table_name='relationship_map_progress')
    op.drop_table('relationship_map_progress')
    op.drop_index('ix_user_specs_prompt_id', table_name='user_specs')
    op.drop_index('ix_user_specs_user_id', table_name='user_specs')
    op.drop_table('user_specs')
    op.drop_index('ix_map_prompts_difficulty_tier', table_name='map_prompts')
    op.drop_index('ix_map_prompts_category', table_name='map_prompts')
    op.drop_table('map_prompts')
