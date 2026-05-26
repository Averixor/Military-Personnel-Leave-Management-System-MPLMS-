"""Initial schema for MPLMS core models.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("normal_overlap_limit", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "policy_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("legal_rules_version", sa.String(length=50), nullable=False),
        sa.Column("internal_policy_version", sa.String(length=50), nullable=False),
        sa.Column("legal_rules", sa.JSON(), nullable=False),
        sa.Column("internal_rules", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_snapshots_is_active", "policy_snapshots", ["is_active"])

    op.create_table(
        "conflict_groups",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("group_type", sa.String(length=50), nullable=False),
        sa.Column("member_personnel_ids", sa.JSON(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_snapshots_snapshot_type", "snapshots", ["snapshot_type"])

    op.create_table(
        "personnel",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("rank", sa.String(length=100), nullable=True),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("commander_id", sa.Integer(), nullable=True),
        sa.Column("deputy_id", sa.Integer(), nullable=True),
        sa.Column("criticality_level", sa.String(length=10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["commander_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["deputy_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_personnel_full_name", "personnel", ["full_name"])
    op.create_index("ix_personnel_telegram_id", "personnel", ["telegram_id"])
    op.create_index("ix_personnel_unit_id", "personnel", ["unit_id"])

    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("desired_start_date", sa.Date(), nullable=False),
        sa.Column("desired_days_count", sa.Integer(), nullable=False),
        sa.Column("destination_locality", sa.String(length=255), nullable=True),
        sa.Column("requested_road_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=80), nullable=False),
        sa.Column("policy_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("selected_option_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["person_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["policy_snapshot_id"], ["policy_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leave_requests_person_id", "leave_requests", ["person_id"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["status"])

    op.create_table(
        "request_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("proposed_start_date", sa.Date(), nullable=False),
        sa.Column("proposed_end_date", sa.Date(), nullable=False),
        sa.Column("conflict_score", sa.Integer(), nullable=False),
        sa.Column("overlap_level", sa.Integer(), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("affected_people_count", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["leave_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_request_options_conflict_score", "request_options", ["conflict_score"])
    op.create_index("ix_request_options_request_id", "request_options", ["request_id"])

    op.create_foreign_key(
        "fk_leave_requests_selected_option_id",
        "leave_requests",
        "request_options",
        ["selected_option_id"],
        ["id"],
    )

    op.create_table(
        "leave_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("leave_type", sa.String(length=50), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("days_count", sa.Integer(), nullable=False),
        sa.Column("initial_starts_on", sa.Date(), nullable=False),
        sa.Column("initial_ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_frozen", sa.Boolean(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("source_request_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["person_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["policy_snapshot_id"], ["policy_snapshots.id"]),
        sa.ForeignKeyConstraint(["source_request_id"], ["leave_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leave_periods_is_frozen", "leave_periods", ["is_frozen"])
    op.create_index("ix_leave_periods_leave_type", "leave_periods", ["leave_type"])
    op.create_index("ix_leave_periods_person_id", "leave_periods", ["person_id"])
    op.create_index("ix_leave_periods_starts_on", "leave_periods", ["starts_on"])
    op.create_index("ix_leave_periods_year", "leave_periods", ["year"])

    op.create_table(
        "road_day_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("leave_period_id", sa.Integer(), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("days_count", sa.Integer(), nullable=False),
        sa.Column("destination_locality", sa.String(length=255), nullable=False),
        sa.Column("distance_km", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["leave_period_id"], ["leave_periods.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["personnel.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_road_day_periods_leave_period_id", "road_day_periods", ["leave_period_id"])
    op.create_index("ix_road_day_periods_person_id", "road_day_periods", ["person_id"])

    op.create_table(
        "affected_person_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("affected_person_id", sa.Integer(), nullable=False),
        sa.Column("affected_leave_id", sa.Integer(), nullable=False),
        sa.Column("proposed_shift_days", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["affected_leave_id"], ["leave_periods.id"]),
        sa.ForeignKeyConstraint(["affected_person_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["leave_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_affected_person_consents_affected_person_id",
        "affected_person_consents",
        ["affected_person_id"],
    )
    op.create_index("ix_affected_person_consents_request_id", "affected_person_consents", ["request_id"])

    op.create_table(
        "approval_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("comment", sa.String(length=1000), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["approver_id"], ["personnel.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["leave_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_steps_approver_id", "approval_steps", ["approver_id"])
    op.create_index("ix_approval_steps_request_id", "approval_steps", ["request_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["leave_requests.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["personnel.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_request_id", "documents", ["request_id"])
    op.create_index("ix_documents_uploaded_by_id", "documents", ["uploaded_by_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_role", sa.String(length=50), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["personnel.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])

    op.create_table(
        "override_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("override_type", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["personnel.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_override_audits_actor_id", "override_audits", ["actor_id"])
    op.create_index("ix_override_audits_override_type", "override_audits", ["override_type"])


def downgrade() -> None:
    op.drop_table("override_audits")
    op.drop_table("audit_logs")
    op.drop_table("documents")
    op.drop_table("approval_steps")
    op.drop_table("affected_person_consents")
    op.drop_table("road_day_periods")
    op.drop_table("leave_periods")
    op.drop_constraint("fk_leave_requests_selected_option_id", "leave_requests", type_="foreignkey")
    op.drop_table("request_options")
    op.drop_table("leave_requests")
    op.drop_table("personnel")
    op.drop_table("snapshots")
    op.drop_table("conflict_groups")
    op.drop_table("policy_snapshots")
    op.drop_table("units")
