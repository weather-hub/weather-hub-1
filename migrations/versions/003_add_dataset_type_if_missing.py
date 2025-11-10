"""add dataset_type column if missing

Revision ID: 003_add_dataset_type_if_missing
Revises: 002
Create Date: 2025-11-10 12:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "003_add_dataset_type_if_missing"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade():
    # Add dataset_type column if it does not exist. Use a compatible SQL
    # statement (MySQL/MariaDB supports `ADD COLUMN IF NOT EXISTS`).
    try:
        op.execute(
            """
            ALTER TABLE data_set
            ADD COLUMN IF NOT EXISTS dataset_type VARCHAR(50) NOT NULL DEFAULT 'uvl'
            """
        )
    except Exception:
        # Fall back to a safe check: attempt to create the column without IF NOT EXISTS
        # and ignore errors if it already exists.
        try:
            op.execute("ALTER TABLE data_set ADD COLUMN dataset_type VARCHAR(50) NOT NULL DEFAULT 'uvl'")
        except Exception:
            # If this also fails, re-raise so migration logs the error and stops.
            raise


def downgrade():
    # Keep downgrade conservative: only drop the column if it exists.
    try:
        op.execute("ALTER TABLE data_set DROP COLUMN IF EXISTS dataset_type")
    except Exception:
        # Some MySQL versions don't support IF EXISTS for DROP COLUMN; attempt naive drop
        try:
            op.execute("ALTER TABLE data_set DROP COLUMN dataset_type")
        except Exception:
            # Ignore failures to avoid accidental destructive behavior during downgrade
            pass
