"""Add DatasetComment table for feedback and questions

Revision ID: 010_add_dataset_comments
Revises: 009_add_ds_metadata_edit_log
Create Date: 2025-12-11
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "010_add_dataset_comments"
down_revision = "009_add_ds_metadata_edit_log"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dataset_comment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["data_set.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dataset_comment_dataset_id"),
        "dataset_comment",
        ["dataset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dataset_comment_created_at"),
        "dataset_comment",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dataset_comment_user_id"),
        "dataset_comment",
        ["user_id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_dataset_comment_user_id"), table_name="dataset_comment")
    op.drop_index(op.f("ix_dataset_comment_created_at"), table_name="dataset_comment")
    op.drop_index(op.f("ix_dataset_comment_dataset_id"), table_name="dataset_comment")
    op.drop_table("dataset_comment")
