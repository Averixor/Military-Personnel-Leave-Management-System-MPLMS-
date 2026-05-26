from mplms.domain.enums import RequestStatus


class InvalidTransition(Exception):
    pass


ALLOWED_TRANSITIONS: dict[RequestStatus, set[RequestStatus]] = {
    RequestStatus.DRAFT: {
        RequestStatus.OPTIONS_GENERATED,
        RequestStatus.CANCELLED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.OPTIONS_GENERATED: {
        RequestStatus.SELECTED_BY_USER,
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
        RequestStatus.CANCELLED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.SELECTED_BY_USER: {
        RequestStatus.WAITING_AFFECTED_PEOPLE,
        RequestStatus.WAITING_ADMIN_REVIEW,
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
        RequestStatus.CANCELLED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.WAITING_AFFECTED_PEOPLE: {
        RequestStatus.WAITING_ADMIN_REVIEW,
        RequestStatus.REJECTED,
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.WAITING_ADMIN_REVIEW: {
        RequestStatus.WAITING_COMMANDER_APPROVAL,
        RequestStatus.REJECTED,
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.WAITING_COMMANDER_APPROVAL: {
        RequestStatus.APPROVED_BY_COMMANDER,
        RequestStatus.REJECTED,
        RequestStatus.EXPIRED,
    },
    RequestStatus.APPROVED_BY_COMMANDER: {
        RequestStatus.READY_TO_APPLY,
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
    },
    RequestStatus.READY_TO_APPLY: {
        RequestStatus.APPLIED,
        RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED,
    },
    RequestStatus.MANUAL_ADMIN_REVIEW_REQUIRED: {
        RequestStatus.WAITING_ADMIN_REVIEW,
        RequestStatus.REJECTED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.APPLIED: set(),
    RequestStatus.REJECTED: set(),
    RequestStatus.EXPIRED: set(),
    RequestStatus.CANCELLED: set(),
}


def validate_transition(current: RequestStatus, target: RequestStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"Invalid leave request transition: {current} -> {target}")


def transition(current: RequestStatus, target: RequestStatus) -> RequestStatus:
    validate_transition(current, target)
    return target

