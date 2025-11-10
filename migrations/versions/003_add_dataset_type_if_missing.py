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
            ADD COLUMN IF NOT EXISTS dataset_type VARCHAR(50) NOT NULL DEFAULT 'uvl',
            ADD COLUMN IF NOT EXISTS storage_path VARCHAR(1024) NULL
            """
        )
    except Exception:
        # Fall back to a safe check: attempt to create the column without IF NOT EXISTS
        # and ignore errors if it already exists.
        try:
            op.execute("ALTER TABLE data_set ADD COLUMN dataset_type VARCHAR(50) NOT NULL DEFAULT 'uvl'")
        except Exception:
            # If adding dataset_type fails, re-raise so migration logs the error and stops.
            raise

        # Try to add storage_path as a best-effort; if it already exists or the DB
        # doesn't support the statement, ignore failures to avoid breaking upgrade.
        try:
            op.execute("ALTER TABLE data_set ADD COLUMN storage_path VARCHAR(1024) NULL")
        except Exception:
            # Ignore failures here (column may already exist or DB may reject NULL-sized types)
            pass


def downgrade():
    # Keep downgrade conservative: only drop the column if it exists.
    try:
        op.execute("ALTER TABLE data_set DROP COLUMN IF EXISTS dataset_type, DROP COLUMN IF EXISTS storage_path")
    except Exception:
        # Some MySQL versions don't support IF EXISTS for DROP COLUMN; attempt naive drop
        try:
            op.execute("ALTER TABLE data_set DROP COLUMN dataset_type")
            try:
                op.execute("ALTER TABLE data_set DROP COLUMN storage_path")
            except Exception:
                pass
        except Exception:
            # Ignore failures to avoid accidental destructive behavior during downgrade
            pass
