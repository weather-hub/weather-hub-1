"""add 2fa fields to user

Revision ID: cf037433030e
Revises: 002
Create Date: 2025-11-08 14:14:58.322278

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf037433030e'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade():
    # Add 2FA fields to user table
    op.add_column('user', sa.Column('otp_secret', sa.String(16), nullable=True))
    op.add_column('user', sa.Column('twofa_enabled', sa.Boolean(), default=False))


def downgrade():
    # Remove 2FA fields from user table
    op.drop_column('user', 'twofa_enabled')
    op.drop_column('user', 'otp_secret')
