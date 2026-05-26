"""Telegram command and message handlers (no business logic)."""

from __future__ import annotations

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy import select

from mplms.bot.database import ensure_personnel_for_telegram
from mplms.bot.database import get_session_factory
from mplms.bot.keyboards import approval_keyboard
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
from mplms.bot.session import SUBMIT_APPROVAL_CALLBACK
from mplms.bot.session import leave_request_sessions
from mplms.bot.session import parse_leave_pick_index
from mplms.bot.session import pick_option
from mplms.cli import DemoFlowResult
from mplms.cli import run_demo_flow
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.personnel import Personnel
from mplms.models.personnel import Unit
from mplms.models.workflow import LeaveRequest
from mplms.services.approval_persistence import approve_by_commander
from mplms.services.approval_persistence import mark_applied
from mplms.services.approval_persistence import mark_ready_to_apply
from mplms.services.approval_persistence import submit_selected_request_for_approval
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option

router = Router()

_HELP_TEXT = (
    "MPLMS — Military Personnel Leave Management System\n\n"
    "Команды:\n"
    "/start — приветствие и меню\n"
    "/help — эта справка\n"
    "/request_leave — создать заявку и выбрать вариант отпуска\n"
    "/my_request — показать активную заявку\n"
    "/commander_approve <request_id> — MVP approval командиром\n"
    "/mark_ready <request_id> — отметить готовой к применению\n"
    "/mark_applied <request_id> — применить заявку\n"
    "/demo_flow — прогнать demo-flow на SQLite (как CLI)\n\n"
    "Кнопки меню дублируют основные действия."
)

DEMO_COMMANDER_NAME = "Telegram Demo Commander"


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

    leave_request_sessions.update_request_id(callback.from_user.id, session.request_id)
    await callback.message.answer(
        f"Заявка #{session.request_id}\n{format_selection_confirmation(option)}",
        reply_markup=approval_keyboard(),
    )


@router.callback_query(F.data == SUBMIT_APPROVAL_CALLBACK)
async def on_submit_approval(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer("Не удалось обработать заявку.", show_alert=True)
        return

    session = leave_request_sessions.get(callback.from_user.id)
    if session is None:
        await callback.answer("Активная заявка не найдена.", show_alert=True)
        await callback.message.answer("Нет активной заявки. Создайте её через /request_leave.")
        return

    await callback.answer("Отправляю на погодження…")
    try:
        session_factory = await get_session_factory()
        async with session_factory() as db_session:
            updated = await submit_selected_request_for_approval(
                db_session,
                request_id=session.request_id,
            )
    except ValueError as exc:
        await callback.message.answer(_friendly_workflow_error(session.request_id, exc))
        return
    except Exception as exc:
        await callback.message.answer(f"Не удалось отправить заявку на погодження:\n{exc}")
        return

    await callback.message.answer(
        f"Заявка #{updated.id} отправлена на погодження.\n"
        f"Статус: {_status_value(updated.status)}",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("commander_approve"))
async def cmd_commander_approve(message: Message) -> None:
    request_id = _request_id_arg(message.text or "")
    if request_id is None:
        await message.answer("Укажите request_id: /commander_approve <request_id>")
        return

    try:
        session_factory = await get_session_factory()
        commander_id = await _ensure_demo_commander(session_factory)
        # TODO: replace demo commander with strict RBAC after auth roles are wired.
        async with session_factory() as session:
            updated = await approve_by_commander(
                session,
                request_id=request_id,
                commander_id=commander_id,
            )
    except ValueError as exc:
        await message.answer(_friendly_workflow_error(request_id, exc))
        return
    except Exception as exc:
        await message.answer(f"Не удалось согласовать заявку:\n{exc}")
        return

    await message.answer(
        f"Заявка #{updated.id} согласована командиром.\n"
        f"Статус: {_status_value(updated.status)}"
    )


@router.message(Command("mark_ready"))
async def cmd_mark_ready(message: Message) -> None:
    request_id = _request_id_arg(message.text or "")
    if request_id is None:
        await message.answer("Укажите request_id: /mark_ready <request_id>")
        return

    try:
        session_factory = await get_session_factory()
        async with session_factory() as session:
            updated = await mark_ready_to_apply(session, request_id=request_id)
    except ValueError as exc:
        await message.answer(_friendly_workflow_error(request_id, exc))
        return
    except Exception as exc:
        await message.answer(f"Не удалось отметить заявку готовой:\n{exc}")
        return

    await message.answer(f"Заявка #{updated.id}\nСтатус: {_status_value(updated.status)}")


@router.message(Command("mark_applied"))
async def cmd_mark_applied(message: Message) -> None:
    request_id = _request_id_arg(message.text or "")
    if request_id is None:
        await message.answer("Укажите request_id: /mark_applied <request_id>")
        return

    try:
        session_factory = await get_session_factory()
        async with session_factory() as session:
            updated = await mark_applied(session, request_id=request_id)
    except ValueError as exc:
        await message.answer(_friendly_workflow_error(request_id, exc))
        return
    except Exception as exc:
        await message.answer(f"Не удалось применить заявку:\n{exc}")
        return

    await message.answer(f"Заявка #{updated.id}\nСтатус: {_status_value(updated.status)}")


@router.message(Command("my_request"))
async def cmd_my_request(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не удалось определить пользователя Telegram.")
        return

    session = leave_request_sessions.get(message.from_user.id)
    if session is None:
        await message.answer("Нет активной заявки. Создайте её через /request_leave.")
        return

    try:
        session_factory = await get_session_factory()
        async with session_factory() as db_session, db_session.begin():
            request = await db_session.get(LeaveRequest, int(session.request_id))
            if request is None:
                await message.answer(f"Заявка #{session.request_id} не найдена.")
                return
            leave_period = None
            if request.selected_leave_period_id is not None:
                leave_period = await db_session.get(
                    LeavePeriod,
                    request.selected_leave_period_id,
                )
    except ValueError:
        await message.answer(f"Некорректный request_id в session: {session.request_id}")
        return
    except Exception as exc:
        await message.answer(f"Не удалось получить заявку:\n{exc}")
        return

    await message.answer(_format_my_request(request, leave_period))


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


def _request_id_arg(text: str) -> str | None:
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    return parts[1].strip()


async def _ensure_demo_commander(session_factory) -> str:
    async with session_factory() as session, session.begin():
        commander = await session.scalar(
            select(Personnel).where(Personnel.full_name == DEMO_COMMANDER_NAME)
        )
        if commander is not None:
            return str(commander.id)

        unit = await session.scalar(select(Unit).where(Unit.name == "Telegram Bot Unit"))
        if unit is None:
            unit = Unit(name="Telegram Bot Unit", normal_overlap_limit=2)
            session.add(unit)
            await session.flush()

        commander = Personnel(
            full_name=DEMO_COMMANDER_NAME,
            role=UserRole.COMMANDER,
            unit_id=unit.id,
        )
        session.add(commander)
        await session.flush()
        return str(commander.id)


def _format_my_request(
    request: LeaveRequest,
    leave_period: LeavePeriod | None,
) -> str:
    lines = [
        f"Заявка #{request.id}",
        f"Статус: {_status_value(request.status)}",
    ]
    if leave_period is not None:
        lines.append(f"Даты: {leave_period.starts_on} — {leave_period.ends_on}")
    return "\n".join(lines)


def _friendly_workflow_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "was not found" in message:
        return f"Заявка #{request_id} не найдена."
    if "must be in" in message:
        return (
            f"Заявка #{request_id} сейчас в неподходящем статусе для этой команды.\n"
            f"Детали: {message}"
        )
    if "Invalid request_id" in message:
        return "Некорректный request_id. Используйте числовой id заявки."
    return f"Не удалось обработать заявку #{request_id}:\n{message}"


def _status_value(status: object) -> str:
    return str(getattr(status, "value", status))
