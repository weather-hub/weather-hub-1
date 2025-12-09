"""Add DSMetaDataEditLog table for tracking minor edits

Revision ID: 009_add_ds_metadata_edit_log
Revises: 008_add_fakenodo_tables
Create Date: 2025-11-30
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "009_add_ds_metadata_edit_log"
down_revision = "008_add_fakenodo_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ds_meta_data_edit_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ds_meta_data_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("edited_at", sa.DateTime(), nullable=False),
        sa.Column("field_name", sa.String(length=50), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("change_summary", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["ds_meta_data_id"], ["ds_meta_data.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_ds_meta_data_edit_log_ds_meta_data_id"),
        "ds_meta_data_edit_log",
        ["ds_meta_data_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ds_meta_data_edit_log_edited_at"),
        "ds_meta_data_edit_log",
        ["edited_at"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_ds_meta_data_edit_log_edited_at"), table_name="ds_meta_data_edit_log")
    op.drop_index(op.f("ix_ds_meta_data_edit_log_ds_meta_data_id"), table_name="ds_meta_data_edit_log")
    op.drop_table("ds_meta_data_edit_log")
