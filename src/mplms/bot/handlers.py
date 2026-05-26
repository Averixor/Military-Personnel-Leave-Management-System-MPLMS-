"""Telegram command and message handlers (no business logic)."""

from __future__ import annotations

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message

from mplms.bot.database import ensure_personnel_for_telegram
from mplms.bot.database import get_session_factory
from mplms.bot.keyboards import BTN_DEMO_REQUEST
from mplms.bot.keyboards import BTN_HELP
from mplms.bot.keyboards import leave_option_keyboard
from mplms.bot.keyboards import main_menu_keyboard
from mplms.bot.leave_request_ui import LEAVE_TYPE_ANNUAL
from mplms.bot.leave_request_ui import REQUEST_DURATION_DAYS
from mplms.bot.leave_request_ui import default_desired_start
from mplms.bot.leave_request_ui import format_options_message
from mplms.bot.leave_request_ui import format_selection_confirmation
from mplms.bot.session import LeaveRequestSession
from mplms.bot.session import leave_request_sessions
from mplms.bot.session import parse_leave_pick_index
from mplms.bot.session import pick_option
from mplms.cli import DemoFlowResult
from mplms.cli import run_demo_flow
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option

router = Router()

_HELP_TEXT = (
    "MPLMS — Military Personnel Leave Management System\n\n"
    "Команды:\n"
    "/start — приветствие и меню\n"
    "/help — эта справка\n"
    "/request_leave — создать заявку и выбрать вариант отпуска\n"
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


@router.message(Command("request_leave"))
async def cmd_request_leave(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    await message.answer("Создаю заявку на отпуск…")
    try:
        session_factory = await get_session_factory()
        personnel_id = await ensure_personnel_for_telegram(
            session_factory,
            message.from_user.id,
            message.from_user.full_name,
        )
        async with session_factory() as session:
            created = await create_persisted_leave_request(
                session,
                personnel_id=personnel_id,
                desired_start=default_desired_start(),
                duration_days=REQUEST_DURATION_DAYS,
                leave_type=LEAVE_TYPE_ANNUAL,
                max_shift_days=14,
            )
    except Exception as exc:
        await message.answer(f"Не удалось создать заявку:\n{exc}")
        return

    if not created.options:
        await message.answer(
            f"Заявка #{created.request_id} создана, но scheduler не нашёл вариантов. "
            f"Статус: {created.status}"
        )
        return

    leave_request_sessions.save(
        message.from_user.id,
        LeaveRequestSession(request_id=created.request_id, options=created.options),
    )
    await message.answer(
        format_options_message(created.request_id, created.options),
        reply_markup=leave_option_keyboard(len(created.options)),
    )


@router.callback_query(F.data.startswith("leave_pick:"))
async def on_leave_option_picked(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer("Не удалось обработать выбор.", show_alert=True)
        return

    index = parse_leave_pick_index(callback.data or "")
    session = leave_request_sessions.get(callback.from_user.id)
    option = pick_option(session, index if index is not None else -1)

    if index is None or session is None or option is None:
        await callback.answer("Недоступный вариант.", show_alert=True)
        return

    await callback.answer("Сохраняю выбор…")
    try:
        session_factory = await get_session_factory()
        async with session_factory() as db_session:
            await select_persisted_leave_option(
                db_session,
                request_id=session.request_id,
                option=option,
            )
    except Exception as exc:
        await callback.message.answer(f"Не удалось выбрать вариант:\n{exc}")
        return

    leave_request_sessions.clear(callback.from_user.id)
    await callback.message.answer(
        f"Заявка #{session.request_id}\n{format_selection_confirmation(option)}",
        reply_markup=main_menu_keyboard(),
    )


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
