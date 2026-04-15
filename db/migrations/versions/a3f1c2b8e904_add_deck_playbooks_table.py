"""add deck_playbooks table (blind playbook native)

Revision ID: a3f1c2b8e904
Revises: 6e07979dba17
Create Date: 2026-04-15 09:00:00.000000

Crea la tabella per il Blind Deck Playbook generato nativamente in App_tool
(Sprint-1 Liberation Day). Schema "per deck + formato": 1 row per (deck, format).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = 'a3f1c2b8e904'
down_revision: Union[str, None] = '6e07979dba17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deck_playbooks',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('deck', sa.String(length=10), nullable=False),
        sa.Column('game_format', sa.String(length=20), nullable=False),
        sa.Column('generated_at', sa.Date(), nullable=False),
        sa.Column('playbook', JSONB(), nullable=False),
        sa.Column('strategic_frame', JSONB(), nullable=True),
        sa.Column('weekly_tech', JSONB(), nullable=True),
        sa.Column('pro_references', JSONB(), nullable=True),
        sa.Column('aggregated', JSONB(), nullable=True),
        sa.Column('meta', JSONB(), nullable=True),
        sa.Column('model', sa.String(length=40), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('cost_usd', sa.Numeric(8, 4), nullable=True),
        sa.Column('digest_count', sa.Integer(), nullable=True),
        sa.Column('total_games', sa.Integer(), nullable=True),
        sa.Column('elapsed_sec', sa.Numeric(7, 2), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.UniqueConstraint('deck', 'game_format', 'generated_at',
                            name='uq_deck_playbooks_deck_format_date'),
    )
    op.create_index(
        'idx_deck_playbooks_lookup',
        'deck_playbooks',
        ['deck', 'game_format', 'is_current'],
        unique=False,
        postgresql_where=sa.text('is_current = true'),
    )


def downgrade() -> None:
    op.drop_index('idx_deck_playbooks_lookup', table_name='deck_playbooks',
                  postgresql_where=sa.text('is_current = true'))
    op.drop_table('deck_playbooks')
