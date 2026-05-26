"""Add personnel import fields.

Revision ID: 003_personnel_import_fields
Revises: 002_selected_leave_period_id
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_personnel_import_fields"
down_revision: Union[str, None] = "002_selected_leave_period_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("personnel", sa.Column("personnel_code", sa.String(length=100), nullable=True))
    op.add_column("personnel", sa.Column("position", sa.String(length=255), nullable=True))
    op.create_index("ix_personnel_personnel_code", "personnel", ["personnel_code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_personnel_personnel_code", table_name="personnel")
    op.drop_column("personnel", "position")
    op.drop_column("personnel", "personnel_code")
