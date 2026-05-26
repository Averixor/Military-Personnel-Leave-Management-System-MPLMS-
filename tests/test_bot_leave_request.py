from datetime import date

from mplms.bot import handlers
from mplms.bot.keyboards import leave_option_keyboard
from mplms.bot.session import LeaveRequestSession
from mplms.bot.session import LeaveRequestSessionStore
from mplms.bot.session import parse_leave_pick_index
from mplms.bot.session import pick_option
from mplms.services.scheduler import ScheduleOption


def _option(day: int) -> ScheduleOption:
    start = date(2026, 7, day)
    end = date(2026, 7, day + 4)
    return ScheduleOption(
        start_date=start,
        end_date=end,
        duration_days=5,
        conflict_score=0,
        overlap_count=0,
        max_absent_on_any_day=1,
        reasons=["ok"],
    )


def test_handlers_import() -> None:
    assert handlers.router is not None


def test_leave_option_keyboard_has_three_buttons() -> None:
    keyboard = leave_option_keyboard(option_count=5)
    assert len(keyboard.inline_keyboard) == 3
    assert keyboard.inline_keyboard[0][0].text == "Выбрать вариант 1"
    assert keyboard.inline_keyboard[1][0].text == "Выбрать вариант 2"
    assert keyboard.inline_keyboard[2][0].text == "Выбрать вариант 3"
    assert keyboard.inline_keyboard[0][0].callback_data == "leave_pick:0"
    assert keyboard.inline_keyboard[2][0].callback_data == "leave_pick:2"


def test_session_store_saves_request_id_and_options() -> None:
    store = LeaveRequestSessionStore()
    options = (_option(1), _option(10), _option(20))
    store.save(42, LeaveRequestSession(request_id="99", options=options))

    loaded = store.get(42)
    assert loaded is not None
    assert loaded.request_id == "99"
    assert len(loaded.options) == 3
    assert loaded.options[1].start_date == date(2026, 7, 10)


def test_pick_option_rejects_invalid_index() -> None:
    session = LeaveRequestSession(request_id="1", options=(_option(1),))
    assert pick_option(session, -1) is None
    assert pick_option(session, 3) is None
    assert pick_option(None, 0) is None
    assert parse_leave_pick_index("leave_pick:abc") is None
    assert parse_leave_pick_index("other:0") is None
    assert pick_option(session, 0) is not None
