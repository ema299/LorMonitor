"""add matchup_reports table

Revision ID: 6e07979dba17
Revises: df9cf2963a28
Create Date: 2026-04-02 12:49:10.277072
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6e07979dba17'
down_revision: Union[str, None] = 'df9cf2963a28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # matchup_reports table already exists (create_new_tables.sql).
    # Align column types with ORM model (TEXT → VARCHAR).
    op.alter_column('matchup_reports', 'game_format',
               existing_type=sa.TEXT(),
               type_=sa.String(length=20),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'our_deck',
               existing_type=sa.TEXT(),
               type_=sa.String(length=10),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'opp_deck',
               existing_type=sa.TEXT(),
               type_=sa.String(length=10),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'report_type',
               existing_type=sa.TEXT(),
               type_=sa.String(length=30),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'is_current',
               existing_type=sa.BOOLEAN(),
               nullable=False,
               existing_server_default=sa.text('true'))
    # Rebuild partial index to include is_current column
    op.drop_index('idx_reports_lookup', table_name='matchup_reports',
                  postgresql_where='(is_current = true)')
    op.create_index('idx_reports_lookup', 'matchup_reports',
                    ['game_format', 'our_deck', 'opp_deck', 'report_type', 'is_current'],
                    unique=False,
                    postgresql_where=sa.text('is_current = true'))


def downgrade() -> None:
    op.drop_index('idx_reports_lookup', table_name='matchup_reports',
                  postgresql_where=sa.text('is_current = true'))
    op.create_index('idx_reports_lookup', 'matchup_reports',
                    ['game_format', 'our_deck', 'opp_deck', 'report_type'],
                    unique=False,
                    postgresql_where='(is_current = true)')
    op.alter_column('matchup_reports', 'is_current',
               existing_type=sa.BOOLEAN(),
               nullable=True,
               existing_server_default=sa.text('true'))
    op.alter_column('matchup_reports', 'report_type',
               existing_type=sa.String(length=30),
               type_=sa.TEXT(),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'opp_deck',
               existing_type=sa.String(length=10),
               type_=sa.TEXT(),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'our_deck',
               existing_type=sa.String(length=10),
               type_=sa.TEXT(),
               existing_nullable=False)
    op.alter_column('matchup_reports', 'game_format',
               existing_type=sa.String(length=20),
               type_=sa.TEXT(),
               existing_nullable=False)
