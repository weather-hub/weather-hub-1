"""add fakenodo tables for SQL storage

Replaces JSON file storage with proper database tables.
Allows Fakenodo to work in ephemeral filesystems (Render, Heroku, etc).

Revision ID: 008_add_fakenodo_tables
Revises: 485dc55cc680
Create Date: 2025-12-07 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "008_add_fakenodo_tables"
down_revision = "485dc55cc680"
branch_labels = None
depends_on = None


def upgrade():
    # Update publication_type enum to only REGIONAL, NATIONAL, CONTINENTAL, OTHER, NONE
    # Update both ds_meta_data and fm_meta_data tables
    for table_name in ["ds_meta_data", "fm_meta_data"]:
        op.execute(
            f"""
            ALTER TABLE {table_name}
            MODIFY COLUMN publication_type ENUM(
                'NONE',
                'REGIONAL',
                'NATIONAL',
                'CONTINENTAL',
                'OTHER'
            ) NOT NULL
        """
        )

    # Create fakenodo_deposition table
    try:
        op.create_table(
            "fakenodo_deposition",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("conceptrecid", sa.Integer(), nullable=False),
            sa.Column("state", sa.String(length=50), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("published", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("dirty", sa.Boolean(), nullable=False, server_default="0"),
            sa.Column("doi", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    except Exception:
        pass

    # Create fakenodo_file table
    try:
        op.create_table(
            "fakenodo_file",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("file_id", sa.String(length=120), nullable=False),
            sa.Column("deposition_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["deposition_id"],
                ["fakenodo_deposition.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("file_id"),
        )
    except Exception:
        pass

    # Create fakenodo_version table
    try:
        op.create_table(
            "fakenodo_version",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("deposition_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("doi", sa.String(length=120), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("files_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["deposition_id"],
                ["fakenodo_deposition.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("doi"),
        )
    except Exception:
        pass


def downgrade():
    # Revert publication_type enum to original simple values
    for table_name in ["ds_meta_data", "fm_meta_data"]:
        op.execute(
            f"""
            ALTER TABLE {table_name}
            MODIFY COLUMN publication_type ENUM(
                'NONE',
                'OTHER'
            ) NOT NULL
        """
        )

    try:
        op.drop_table("fakenodo_version")
    except Exception:
        pass

    try:
        op.drop_table("fakenodo_file")
    except Exception:
        pass

    try:
        op.drop_table("fakenodo_deposition")
    except Exception:
        pass
