"""add community tables
Revision ID: 006_add_user_sessions
Revises: 005_add_community
Create Date: 2025-12-03 14:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '006_add_user_sessions'
down_revision = '005_add_community'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(length=256), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=512), nullable=True),
        sa.Column('device_info', sa.String(length=256), nullable=True),
        sa.Column('location', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_activity', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id'),
    )
    # create index on session_id for faster lookups
    op.create_index(op.f('ix_user_session_session_id'), 'user_session', ['session_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_session_session_id'), table_name='user_session')
    op.drop_table('user_session')