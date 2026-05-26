"""In-memory leave request sessions for Telegram MVP."""

from __future__ import annotations

from dataclasses import dataclass

from mplms.services.scheduler import ScheduleOption

MAX_PICKABLE_OPTIONS = 3
LEAVE_PICK_PREFIX = "leave_pick:"
SUBMIT_APPROVAL_CALLBACK = "leave_submit_approval"


@dataclass(frozen=True)
class LeaveRequestSession:
    request_id: str
    options: tuple[ScheduleOption, ...]


class LeaveRequestSessionStore:
    """Temporary MVP storage keyed by Telegram user id."""

    def __init__(self) -> None:
        self._sessions: dict[int, LeaveRequestSession] = {}

    def save(self, telegram_user_id: int, session: LeaveRequestSession) -> None:
        self._sessions[telegram_user_id] = session

    def get(self, telegram_user_id: int) -> LeaveRequestSession | None:
        return self._sessions.get(telegram_user_id)

    def clear(self, telegram_user_id: int) -> None:
        self._sessions.pop(telegram_user_id, None)

    def update_request_id(self, telegram_user_id: int, request_id: str) -> None:
        session = self._sessions.get(telegram_user_id)
        if session is None:
            self._sessions[telegram_user_id] = LeaveRequestSession(
                request_id=request_id,
                options=(),
            )
            return
        self._sessions[telegram_user_id] = LeaveRequestSession(
            request_id=request_id,
            options=session.options,
        )


def parse_leave_pick_index(callback_data: str) -> int | None:
    if not callback_data.startswith(LEAVE_PICK_PREFIX):
        return None
    try:
        return int(callback_data.removeprefix(LEAVE_PICK_PREFIX))
    except ValueError:
        return None


def pick_option(
    session: LeaveRequestSession | None,
    index: int,
    *,
    max_options: int = MAX_PICKABLE_OPTIONS,
) -> ScheduleOption | None:
    if session is None or index < 0 or index >= max_options:
        return None
    if index >= len(session.options):
        return None
    return session.options[index]


# Shared store for the bot process (MVP only).
leave_request_sessions = LeaveRequestSessionStore()
