"""Add selected_leave_period_id to leave_requests.

Revision ID: 002_selected_leave_period_id
Revises: 001_initial_schema
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_selected_leave_period_id"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_requests",
        sa.Column("selected_leave_period_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_leave_requests_selected_leave_period_id",
        "leave_requests",
        "leave_periods",
        ["selected_leave_period_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_leave_requests_selected_leave_period_id",
        "leave_requests",
        type_="foreignkey",
    )
    op.drop_column("leave_requests", "selected_leave_period_id")
