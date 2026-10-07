"""prompts and responses (conversational elicitation)

Revision ID: a3f1c2d4e5b6
Revises: 6edfedde05d8
Create Date: 2026-10-07 08:40:00
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = 'a3f1c2d4e5b6'
down_revision = '6edfedde05d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    prompt_kind = postgresql.ENUM('question', 'translate', 'word', name='prompt_kind', create_type=False)
    prompt_kind.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'prompts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False),
        sa.Column('kind', prompt_kind, nullable=False),
        sa.Column('text_en', sa.Text(), nullable=False),
        sa.Column('text_hi', sa.Text(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('response_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('text_en', name='uq_prompt_text_en'),
    )
    op.create_index('ix_prompts_active_category', 'prompts', ['active', 'category'])

    op.create_table(
        'responses',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('prompt_id', sa.UUID(), nullable=False),
        sa.Column('contributor_id', sa.UUID(), nullable=False),
        sa.Column('lang', sa.String(length=8), nullable=False),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('normalized', sa.Text(), nullable=True),
        sa.Column('sentence_id', sa.UUID(), nullable=True),
        sa.Column('pool_reason', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['prompt_id'], ['prompts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contributor_id'], ['contributors.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['sentence_id'], ['sentences.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_responses_prompt', 'responses', ['prompt_id'])
    op.create_index('ix_responses_contributor_lang', 'responses', ['contributor_id', 'lang'])

    # A recording may now answer a prompt instead of reading a sentence.
    op.alter_column('recordings', 'sentence_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('recordings', sa.Column('response_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_recordings_response', 'recordings', 'responses', ['response_id'], ['id'], ondelete='CASCADE'
    )
    op.create_index('ix_recordings_response', 'recordings', ['response_id'])
    op.create_check_constraint(
        'ck_recordings_has_target', 'recordings', 'sentence_id IS NOT NULL OR response_id IS NOT NULL'
    )


def downgrade() -> None:
    op.drop_constraint('ck_recordings_has_target', 'recordings', type_='check')
    op.drop_index('ix_recordings_response', table_name='recordings')
    op.drop_constraint('fk_recordings_response', 'recordings', type_='foreignkey')
    op.drop_column('recordings', 'response_id')
    op.execute('DELETE FROM recordings WHERE sentence_id IS NULL')
    op.alter_column('recordings', 'sentence_id', existing_type=sa.UUID(), nullable=False)
    op.drop_index('ix_responses_contributor_lang', table_name='responses')
    op.drop_index('ix_responses_prompt', table_name='responses')
    op.drop_table('responses')
    op.drop_index('ix_prompts_active_category', table_name='prompts')
    op.drop_table('prompts')
    sa.Enum(name='prompt_kind').drop(op.get_bind(), checkfirst=True)
