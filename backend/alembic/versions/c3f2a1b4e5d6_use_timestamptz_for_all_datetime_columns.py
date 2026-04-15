"""use timestamptz for all datetime columns

Revision ID: c3f2a1b4e5d6
Revises: 847a8801711e
Create Date: 2026-03-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3f2a1b4e5d6'
down_revision: Union[str, Sequence[str], None] = '847a8801711e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columns to migrate: (table, column)
_COLUMNS = [
    ("scan_jobs", "created_at"),
    ("scan_jobs", "updated_at"),
    ("findings", "created_at"),
    ("scan_schedules", "created_at"),
    ("scan_schedules", "last_run_at"),
    ("scan_schedules", "next_run_at"),
    ("audit_logs", "created_at"),
    ("discovered_keywords", "first_seen_at"),
    ("discovered_keywords", "approved_at"),
    ("users", "created_at"),
    ("users", "last_login_at"),
]


def upgrade() -> None:
    conn = op.get_bind()
    existing = sa.inspect(conn).get_table_names()
    if "scan_jobs" not in existing:
        # Fresh install - create_all will use DateTime(timezone=True) directly.
        return
    for table, column in _COLUMNS:
        if table in existing:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITH TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )


def downgrade() -> None:
    conn = op.get_bind()
    existing = sa.inspect(conn).get_table_names()
    for table, column in _COLUMNS:
        if table in existing:
            op.execute(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )
