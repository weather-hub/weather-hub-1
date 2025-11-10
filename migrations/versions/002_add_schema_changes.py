"""add fields and rename columns to match desired schema

Revision ID: 002
Revises: 001
Create Date: 2025-11-10 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    # add new columns to existing tables
    op.add_column(
        "user",
        sa.Column("otp_secret", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "user",
        sa.Column(
            "twofa_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.add_column(
        "data_set",
        sa.Column("dataset_type", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "data_set",
        sa.Column("storage_path", sa.String(length=255), nullable=True),
    )

    # rename columns in fm_meta_data: uvl_filename -> filename, uvl_version -> version
    # use alter_column with new_column_name where supported
    try:
        op.alter_column("fm_meta_data", "uvl_filename", new_column_name="filename")
    except Exception:
        # fallback: try raw SQL (MySQL/Postgres differ) — best-effort, may need manual tweak per DB
        op.execute("ALTER TABLE fm_meta_data RENAME COLUMN uvl_filename TO filename")

    try:
        op.alter_column("fm_meta_data", "uvl_version", new_column_name="version")
    except Exception:
        op.execute("ALTER TABLE fm_meta_data RENAME COLUMN uvl_version TO version")


def downgrade():
    # revert renamed columns
    try:
        op.alter_column("fm_meta_data", "filename", new_column_name="uvl_filename")
    except Exception:
        op.execute("ALTER TABLE fm_meta_data RENAME COLUMN filename TO uvl_filename")

    try:
        op.alter_column("fm_meta_data", "version", new_column_name="uvl_version")
    except Exception:
        op.execute("ALTER TABLE fm_meta_data RENAME COLUMN version TO uvl_version")

    # drop added columns
    op.drop_column("data_set", "storage_path")
    op.drop_column("data_set", "dataset_type")
    op.drop_column("user", "twofa_enabled")
    op.drop_column("user", "otp_secret")
