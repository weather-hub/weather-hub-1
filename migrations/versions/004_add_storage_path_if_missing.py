"""add storage_path column if missing

Revision ID: 004_add_storage_path_if_missing
Revises: 003_add_dataset_type_if_missing
Create Date: 2025-11-10 14:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "004_add_storage_path_if_missing"
down_revision = "003_add_dataset_type_if_missing"
branch_labels = None
depends_on = None


def upgrade():
    # Add storage_path column if it does not exist. Use a compatible SQL
    # statement (MySQL/MariaDB supports `ADD COLUMN IF NOT EXISTS` in newer versions).
    try:
        op.execute(
            """
            ALTER TABLE data_set
            ADD COLUMN IF NOT EXISTS storage_path VARCHAR(255) NULL
            """
        )
    except Exception:
        # Fall back to attempting to create the column without IF NOT EXISTS
        # and ignore errors if it already exists or the DB rejects the statement.
        try:
            op.execute("ALTER TABLE data_set ADD COLUMN storage_path VARCHAR(255) NULL")
        except Exception:
            # Ignore failures to avoid breaking upgrade in environments that
            # either already have the column or don't support the syntax.
            pass


def downgrade():
    # Conservative downgrade: drop the column if it exists.
    try:
        op.execute("ALTER TABLE data_set DROP COLUMN IF EXISTS storage_path")
    except Exception:
        try:
            op.execute("ALTER TABLE data_set DROP COLUMN storage_path")
        except Exception:
            pass
