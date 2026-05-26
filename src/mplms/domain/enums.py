from enum import StrEnum


class UserRole(StrEnum):
    PERSONNEL = "personnel"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    COMMANDER = "commander"
    DEPUTY_COMMANDER = "deputy_commander"


class CriticalityLevel(StrEnum):
    NORMAL = "0"
    IMPORTANT = "1"
    CRITICAL = "2"
    STRATEGIC = "3"


class LeaveType(StrEnum):
    ANNUAL_MAIN = "annual_main"
    ANNUAL_SECOND_PART = "annual_second_part"
    FAMILY = "family"
    UBD = "ubd"
    COMBAT_REWARD = "combat_reward"
    MEDICAL = "medical"
    CAPTIVITY_RECOVERY = "captivity_recovery"
    ROAD_DAYS = "road_days"
    OTHER_SPECIAL = "other_special"


class LeaveStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RequestStatus(StrEnum):
    DRAFT = "draft"
    OPTIONS_GENERATED = "options_generated"
    SELECTED_BY_USER = "selected_by_user"
    WAITING_AFFECTED_PEOPLE = "waiting_affected_people"
    WAITING_ADMIN_REVIEW = "waiting_admin_review"
    WAITING_COMMANDER_APPROVAL = "waiting_commander_approval"
    APPROVED_BY_COMMANDER = "approved_by_commander"
    READY_TO_APPLY = "ready_to_apply"
    APPLIED = "applied"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    MANUAL_ADMIN_REVIEW_REQUIRED = "manual_admin_review_required"


class ConsentStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ConflictGroupType(StrEnum):
    PAIR = "pair"
    GROUP = "group"
    HIERARCHY_CHAIN = "hierarchy_chain"

