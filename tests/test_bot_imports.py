from unittest.mock import patch

import pytest

from mplms.bot import handlers
from mplms.bot import keyboards
from mplms.bot import main as bot_main
from mplms.bot.handlers import format_demo_flow_result
from mplms.bot.keyboards import BTN_HELP
from mplms.bot.keyboards import BTN_MY_REQUESTS
from mplms.bot.keyboards import BTN_SUBMIT_LEAVE
from mplms.bot.keyboards import main_menu_keyboard
from mplms.cli import AuditEventSummary
from mplms.cli import DemoFlowResult


def test_bot_main_imports() -> None:
    assert callable(bot_main.main)
    assert callable(bot_main.resolve_telegram_token)
    assert callable(bot_main.create_dispatcher)


def test_handlers_import() -> None:
    assert handlers.router is not None
    assert callable(format_demo_flow_result)


def test_keyboards_import() -> None:
    keyboard = main_menu_keyboard()
    texts = {button.text for row in keyboard.keyboard for button in row}
    assert BTN_SUBMIT_LEAVE in texts
    assert BTN_MY_REQUESTS in texts
    assert BTN_HELP in texts


def test_format_demo_flow_result() -> None:
    result = DemoFlowResult(
        request_id="1",
        personnel_id="10",
        commander_id="20",
        final_status="applied",
        audit_events=(
            AuditEventSummary(
                action="applied",
                before_state={"status": "ready_to_apply"},
                after_state={"status": "applied"},
            ),
        ),
    )
    text = format_demo_flow_result(result)
    assert "внесено в графік" in text
    assert "№1" in text
    assert "Personnel id" not in text
    assert "Demo-flow" not in text


def test_missing_token_prints_clear_message(capsys: pytest.CaptureFixture[str]) -> None:
    with patch.object(bot_main, "resolve_telegram_token", return_value=None):
        exit_code = bot_main.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert bot_main.NOT_CONFIGURED_MESSAGE in captured.out
