"""Telegram command and message handlers (no business logic)."""

from __future__ import annotations

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from mplms.bot.keyboards import BTN_DEMO_REQUEST
from mplms.bot.keyboards import BTN_HELP
from mplms.bot.keyboards import main_menu_keyboard
from mplms.cli import DemoFlowResult
from mplms.cli import run_demo_flow

router = Router()

_HELP_TEXT = (
    "MPLMS — Military Personnel Leave Management System\n\n"
    "Команды:\n"
    "/start — приветствие и меню\n"
    "/help — эта справка\n"
    "/demo_flow — прогнать demo-flow на SQLite (как CLI)\n\n"
    "Кнопки меню дублируют основные действия."
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Добро пожаловать в MPLMS.\n"
        "Бот — тонкий UI-слой; бизнес-логика выполняется в backend-сервисах.\n\n"
        "Используйте /help или кнопки ниже.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(_HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("demo_flow"))
@router.message(F.text == BTN_DEMO_REQUEST)
async def cmd_demo_flow(message: Message) -> None:
    await message.answer("Запускаю demo-flow на dev SQLite…")
    try:
        result = await run_demo_flow(verbose=False)
    except Exception as exc:
        await message.answer(f"Demo-flow завершился с ошибкой:\n{exc}")
        return

    await message.answer(format_demo_flow_result(result), reply_markup=main_menu_keyboard())


def format_demo_flow_result(result: DemoFlowResult) -> str:
    lines = [
        "Demo-flow завершён.",
        f"Заявка: #{result.request_id}",
        f"Personnel id: {result.personnel_id}",
        f"Commander id: {result.commander_id}",
        f"Финальный статус: {result.final_status}",
        "",
        "Audit trail:",
    ]
    for event in result.audit_events:
        before = event.before_state or {}
        after = event.after_state or {}
        lines.append(f"• {event.action}: {before} → {after}")
    return "\n".join(lines)
