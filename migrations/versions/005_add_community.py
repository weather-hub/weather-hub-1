"""add community tables



Revision ID: 005_add_community


Revises: 004_add_storage_path_if_missing


Create Date: 2025-11-10 14:30:00.000000




"""

import sqlalchemy as sa
from alembic import op

revision = "005_add_community"
down_revision = "004_add_storage_path_if_missing"
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.create_table(
            "community",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("visual_identity", sa.String(length=1024), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name"),
        )
    except Exception:
        pass

    try:
        op.create_table(
            "community_curators",
            sa.Column("community_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["community_id"], ["community.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("community_id", "user_id"),
        )
    except Exception:
        pass
    try:
        op.create_table(
            "community_dataset_proposal",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("community_id", sa.Integer(), nullable=False),
            sa.Column("dataset_id", sa.Integer(), nullable=False),
            sa.Column("proposed_by", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["community_id"], ["community.id"]),
            sa.ForeignKeyConstraint(["dataset_id"], ["data_set.id"]),
            sa.ForeignKeyConstraint(["proposed_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    except Exception:
        pass


def downgrade():
    try:
        op.drop_table("community_dataset_proposal")
    except Exception:
        pass
    try:
        op.drop_table("community_curators")
    except Exception:
        pass
    try:
        op.drop_table("community")
    except Exception:
        pass
