import pytest

from mplms.domain.enums import RequestStatus
from mplms.services.workflow import InvalidTransition
from mplms.services.workflow import transition


def test_valid_transition_to_generated_options() -> None:
    assert (
        transition(RequestStatus.DRAFT, RequestStatus.OPTIONS_GENERATED)
        == RequestStatus.OPTIONS_GENERATED
    )


def test_rejects_direct_apply_from_draft() -> None:
    with pytest.raises(InvalidTransition):
        transition(RequestStatus.DRAFT, RequestStatus.APPLIED)


def test_applied_is_terminal() -> None:
    with pytest.raises(InvalidTransition):
        transition(RequestStatus.APPLIED, RequestStatus.READY_TO_APPLY)

