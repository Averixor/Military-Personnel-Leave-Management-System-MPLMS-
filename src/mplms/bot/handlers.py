"""Telegram command and message handlers (no business logic)."""

from __future__ import annotations

from aiogram import F
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from aiogram.types import Message
from sqlalchemy import desc
from sqlalchemy import select

from mplms.bot.auth import RoleRequiredError
from mplms.bot.auth import require_role
from mplms.bot.database import ensure_personnel_for_telegram
from mplms.bot.database import get_session_factory
from mplms.bot.database import InactivePersonnelError
from mplms.bot.database import PERSONNEL_NOT_IN_DATABASE_MESSAGE
from mplms.bot.database import TelegramPersonnelNotFoundError
from mplms.bot.keyboards import admin_actions_keyboard
from mplms.bot.keyboards import admin_menu_keyboard
from mplms.bot.keyboards import approval_keyboard
from mplms.bot.keyboards import BTN_ADMIN_ACTIONS
from mplms.bot.keyboards import BTN_COMMANDER_PENDING
from mplms.bot.keyboards import BTN_HELP
from mplms.bot.keyboards import BTN_MY_REQUESTS
from mplms.bot.keyboards import BTN_SUBMIT_LEAVE
from mplms.bot.keyboards import commander_menu_keyboard
from mplms.bot.keyboards import commander_pending_keyboard
from mplms.bot.keyboards import leave_option_keyboard
from mplms.bot.keyboards import main_menu_keyboard
from mplms.bot.leave_request_ui import format_admin_actions_list
from mplms.bot.leave_request_ui import format_no_options_message
from mplms.bot.leave_request_ui import format_options_message
from mplms.bot.leave_request_ui import format_pending_commander_list
from mplms.bot.leave_request_ui import format_request_list_status
from mplms.bot.leave_request_ui import format_request_status
from mplms.bot.leave_request_ui import LEAVE_TYPE_ANNUAL
from mplms.bot.leave_request_ui import REQUEST_DURATION_DAYS
from mplms.bot.leave_request_ui import default_desired_start
from mplms.bot.leave_request_ui import request_status_label
from mplms.bot.session import ADMIN_MARK_APPLIED_PREFIX
from mplms.bot.session import ADMIN_MARK_READY_PREFIX
from mplms.bot.session import COMMANDER_APPROVE_PREFIX
from mplms.bot.session import LeaveRequestSession
from mplms.bot.session import leave_request_sessions
from mplms.bot.session import parse_leave_pick_index
from mplms.bot.session import parse_request_id_callback
from mplms.bot.session import pick_option
from mplms.bot.session import SUBMIT_APPROVAL_CALLBACK
from mplms.cli import DemoFlowResult
from mplms.cli import run_demo_flow
from mplms.core.config import get_settings
from mplms.domain.enums import LeaveStatus
from mplms.domain.enums import RequestStatus
from mplms.domain.enums import UserRole
from mplms.models.leave import LeavePeriod
from mplms.models.workflow import LeaveRequest
from mplms.services.approval_persistence import approve_by_commander
from mplms.services.approval_persistence import mark_applied
from mplms.services.approval_persistence import mark_ready_to_apply
from mplms.services.approval_persistence import submit_selected_request_for_approval
from mplms.services.leave_request_persistence import create_persisted_leave_request
from mplms.services.leave_request_persistence import select_persisted_leave_option

router = Router()

_HELP_TEXT = (
    "MPLMS — система обліку відпусток військовослужбовців\n\n"
    "Основні дії — кнопками в меню:\n"
    "• Подати заявку на відпустку\n"
    "• Мої заявки\n"
    "• Допомога\n\n"
    "Для командира:\n"
    "• Заявки на погодження — список і кнопка «Погодити»\n\n"
    "Для адміністратора:\n"
    "• Адмін-дії — позначити готовою / внести в графік\n\n"
    "Резервні команди (за потреби):\n"
    "/start — головне меню\n"
    "/request_leave — подати заявку\n"
    "/my_request — активна заявка з сесії\n"
    "/my_requests — ваші заявки\n"
    "/cancel_request — скасувати заявку до внесення в графік\n"
    "/commander_pending — заявки на погодження (командир)\n"
    "/admin_actions — адмін-дії"
)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Вітаємо в MPLMS.\n"
        "Оберіть дію кнопками нижче або скористайтеся /help.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(_HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("request_leave"))
@router.message(F.text == BTN_SUBMIT_LEAVE)
async def cmd_request_leave(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    await message.answer("Створюю заявку на відпустку…")
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
                personnel_id=str(personnel_id.id),
                desired_start=default_desired_start(),
                duration_days=REQUEST_DURATION_DAYS,
                leave_type=LEAVE_TYPE_ANNUAL,
                max_shift_days=14,
            )
    except (InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        await message.answer(_friendly_personnel_error(exc))
        return
    except Exception:
        await message.answer("Не вдалося створити заявку. Спробуйте пізніше.")
        return

    if not created.options:
        await message.answer(format_no_options_message(created.request_id))
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
        await callback.answer("Не вдалося обробити вибір.", show_alert=True)
        return

    index = parse_leave_pick_index(callback.data or "")
    session = leave_request_sessions.get(callback.from_user.id)
    option = pick_option(session, index if index is not None else -1)

    if index is None or session is None or option is None:
        await callback.answer("Недоступний варіант.", show_alert=True)
        return

    await callback.answer("Зберігаю вибір…")
    try:
        session_factory = await get_session_factory()
        async with session_factory() as db_session:
            updated = await select_persisted_leave_option(
                db_session,
                request_id=session.request_id,
                option=option,
            )
            selected_leave_period = await _load_selected_leave_period(db_session, updated)
    except ValueError as exc:
        await callback.message.answer(
            await _friendly_pick_error(session.request_id, exc)
        )
        return
    except Exception:
        await callback.message.answer("Не вдалося зберегти вибір. Спробуйте пізніше.")
        return

    leave_request_sessions.update_request_id(callback.from_user.id, session.request_id)
    await callback.message.answer(
        format_request_status(updated, selected_leave_period),
        reply_markup=approval_keyboard(),
    )


@router.callback_query(F.data == SUBMIT_APPROVAL_CALLBACK)
async def on_submit_approval(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer("Не вдалося обробити заявку.", show_alert=True)
        return

    session = leave_request_sessions.get(callback.from_user.id)
    if session is None:
        await callback.answer("Активну заявку не знайдено.", show_alert=True)
        await callback.message.answer(
            "Немає активної заявки. Створіть її через «Подати заявку на відпустку»."
        )
        return

    await callback.answer("Відправляю на погодження…")
    try:
        session_factory = await get_session_factory()
        async with session_factory() as db_session:
            updated = await submit_selected_request_for_approval(
                db_session,
                request_id=session.request_id,
            )
            selected_leave_period = await _load_selected_leave_period(db_session, updated)
    except ValueError as exc:
        await callback.message.answer(
            await _friendly_submit_error(session.request_id, exc)
        )
        return
    except Exception:
        await callback.message.answer(
            "Не вдалося відправити заявку на погодження. Спробуйте пізніше."
        )
        return

    await callback.message.answer(
        format_request_status(updated, selected_leave_period),
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("commander_pending"))
@router.message(F.text == BTN_COMMANDER_PENDING)
async def cmd_commander_pending(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    try:
        session_factory = await get_session_factory()
        async with session_factory() as auth_session:
            await require_role(
                auth_session,
                message.from_user.id,
                {UserRole.COMMANDER.value},
            )
        items = await _load_requests_by_status(
            session_factory,
            status=RequestStatus.WAITING_COMMANDER_APPROVAL,
        )
    except (RoleRequiredError, InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        await message.answer(_friendly_access_error(exc))
        return
    except Exception:
        await message.answer("Не вдалося завантажити заявки. Спробуйте пізніше.")
        return

    request_ids = tuple(str(request.id) for request, _ in items)
    await message.answer(
        format_pending_commander_list(items),
        reply_markup=commander_pending_keyboard(request_ids) if request_ids else None,
    )


@router.message(Command("admin_actions"))
@router.message(F.text == BTN_ADMIN_ACTIONS)
async def cmd_admin_actions(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    try:
        session_factory = await get_session_factory()
        async with session_factory() as auth_session:
            await require_role(
                auth_session,
                message.from_user.id,
                {UserRole.ADMIN.value},
            )
        approved = await _load_requests_by_status(
            session_factory,
            status=RequestStatus.APPROVED_BY_COMMANDER,
        )
        ready = await _load_requests_by_status(
            session_factory,
            status=RequestStatus.READY_TO_APPLY,
        )
    except (RoleRequiredError, InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        await message.answer(_friendly_access_error(exc))
        return
    except Exception:
        await message.answer("Не вдалося завантажити заявки. Спробуйте пізніше.")
        return

    approved_ids = tuple(str(request.id) for request, _ in approved)
    ready_ids = tuple(str(request.id) for request, _ in ready)
    keyboard = None
    if approved_ids or ready_ids:
        keyboard = admin_actions_keyboard(
            approved_ids=approved_ids,
            ready_ids=ready_ids,
        )
    await message.answer(
        format_admin_actions_list(approved, ready),
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith(COMMANDER_APPROVE_PREFIX))
async def on_commander_approve_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer("Не вдалося обробити заявку.", show_alert=True)
        return

    request_id = parse_request_id_callback(
        callback.data or "",
        prefix=COMMANDER_APPROVE_PREFIX,
    )
    if request_id is None:
        await callback.answer("Некоректна заявка.", show_alert=True)
        return

    await callback.answer("Погоджую…")
    text, _ = await _run_commander_approve(callback.from_user.id, request_id)
    await callback.message.answer(text, reply_markup=commander_menu_keyboard())


@router.callback_query(F.data.startswith(ADMIN_MARK_READY_PREFIX))
async def on_admin_mark_ready_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer("Не вдалося обробити заявку.", show_alert=True)
        return

    request_id = parse_request_id_callback(
        callback.data or "",
        prefix=ADMIN_MARK_READY_PREFIX,
    )
    if request_id is None:
        await callback.answer("Некоректна заявка.", show_alert=True)
        return

    await callback.answer("Оновлюю статус…")
    text, _ = await _run_mark_ready(callback.from_user.id, request_id)
    await callback.message.answer(text, reply_markup=admin_menu_keyboard())


@router.callback_query(F.data.startswith(ADMIN_MARK_APPLIED_PREFIX))
async def on_admin_mark_applied_callback(callback: CallbackQuery) -> None:
    if callback.from_user is None or callback.message is None:
        await callback.answer("Не вдалося обробити заявку.", show_alert=True)
        return

    request_id = parse_request_id_callback(
        callback.data or "",
        prefix=ADMIN_MARK_APPLIED_PREFIX,
    )
    if request_id is None:
        await callback.answer("Некоректна заявка.", show_alert=True)
        return

    await callback.answer("Вношу в графік…")
    text, _ = await _run_mark_applied(callback.from_user.id, request_id)
    await callback.message.answer(text, reply_markup=admin_menu_keyboard())


@router.message(Command("commander_approve"))
async def cmd_commander_approve(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    request_id = _request_id_arg(message.text or "")
    if request_id is None:
        await message.answer(
            "Оберіть заявку через кнопку «Заявки на погодження»."
        )
        return

    text, keyboard = await _run_commander_approve(message.from_user.id, request_id)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("mark_ready"))
async def cmd_mark_ready(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    request_id = _request_id_arg(message.text or "")
    if request_id is None:
        await message.answer(
            "Оберіть заявку через кнопку «Адмін-дії»."
        )
        return

    text, keyboard = await _run_mark_ready(message.from_user.id, request_id)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("mark_applied"))
async def cmd_mark_applied(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    request_id = _request_id_arg(message.text or "")
    if request_id is None:
        await message.answer(
            "Оберіть заявку через кнопку «Адмін-дії»."
        )
        return

    text, keyboard = await _run_mark_applied(message.from_user.id, request_id)
    await message.answer(text, reply_markup=keyboard)


@router.message(Command("my_request"))
async def cmd_my_request(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    session = leave_request_sessions.get(message.from_user.id)
    if session is None:
        await message.answer(
            "Немає активної заявки в сесії. Перегляньте «Мої заявки» або створіть нову."
        )
        return

    try:
        session_factory = await get_session_factory()
        async with session_factory() as db_session, db_session.begin():
            request = await db_session.get(LeaveRequest, int(session.request_id))
            if request is None:
                await message.answer(f"Заявку №{session.request_id} не знайдено.")
                return
            leave_period = await _load_selected_leave_period(db_session, request)
    except ValueError:
        await message.answer("Некоректний номер заявки в сесії.")
        return
    except Exception:
        await message.answer("Не вдалося отримати заявку. Спробуйте пізніше.")
        return

    await message.answer(format_request_status(request, leave_period))


@router.message(Command("my_requests"))
@router.message(F.text == BTN_MY_REQUESTS)
async def cmd_my_requests(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    try:
        session_factory = await get_session_factory()
        personnel_id = await ensure_personnel_for_telegram(
            session_factory,
            message.from_user.id,
            message.from_user.full_name,
        )
        async with session_factory() as db_session, db_session.begin():
            result = await db_session.execute(
                select(LeaveRequest)
                .where(LeaveRequest.person_id == personnel_id.id)
                .order_by(desc(LeaveRequest.id))
                .limit(10)
            )
            requests = tuple(result.scalars())
    except (InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        await message.answer(_friendly_personnel_error(exc))
        return
    except Exception:
        await message.answer("Не вдалося отримати список заявок. Спробуйте пізніше.")
        return

    if not requests:
        await message.answer(
            "У вас поки немає заявок. Натисніть «Подати заявку на відпустку»."
        )
        return

    await message.answer(format_request_list_status(requests))


@router.message(Command("cancel_request"))
async def cmd_cancel_request(message: Message) -> None:
    if message.from_user is None:
        await message.answer("Не вдалося визначити користувача Telegram.")
        return

    session = leave_request_sessions.get(message.from_user.id)
    request_id = _request_id_arg(message.text or "") or (
        session.request_id if session is not None else None
    )
    if request_id is None:
        await message.answer(
            "Немає активної заявки. Відкрийте «Мої заявки» або створіть нову."
        )
        return

    try:
        request_pk = int(request_id)
    except ValueError:
        await message.answer("Некоректний номер заявки.")
        return

    try:
        session_factory = await get_session_factory()
        personnel_id = await ensure_personnel_for_telegram(
            session_factory,
            message.from_user.id,
            message.from_user.full_name,
        )
        async with session_factory() as db_session, db_session.begin():
            request = await db_session.get(LeaveRequest, request_pk)
            if request is None or request.person_id != personnel_id.id:
                await message.answer(f"Заявку №{request_id} не знайдено серед ваших заявок.")
                return
            leave_period = await _load_selected_leave_period(db_session, request)
            if request.status == RequestStatus.APPLIED:
                await message.answer(
                    "Заявку вже внесено в графік. Скасувати її через бот неможливо.\n\n"
                    f"{format_request_status(request, leave_period)}"
                )
                return
            if request.status == RequestStatus.CANCELLED:
                await message.answer(
                    "Заявку вже скасовано.\n\n"
                    f"{format_request_status(request, leave_period)}"
                )
                return

            request.status = RequestStatus.CANCELLED
            selected_leave_period = leave_period
            if request.selected_leave_period_id is not None and leave_period is not None:
                leave_period.status = LeaveStatus.CANCELLED
            await db_session.flush()
    except (InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        await message.answer(_friendly_personnel_error(exc))
        return
    except Exception:
        await message.answer("Не вдалося скасувати заявку. Спробуйте пізніше.")
        return

    await message.answer(format_request_status(request, selected_leave_period))


@router.message(Command("demo_flow"))
async def cmd_demo_flow(message: Message) -> None:
    if not _demo_flow_enabled():
        await message.answer(_GENERIC_ACTION_ERROR)
        return

    await message.answer("Виконую перевірку…")
    try:
        result = await run_demo_flow(verbose=False)
    except Exception:
        await message.answer(_GENERIC_ACTION_ERROR)
        return

    await message.answer(format_demo_flow_result(result), reply_markup=main_menu_keyboard())


_GENERIC_ACTION_ERROR = "Не вдалося виконати дію. Спробуйте пізніше."


def _demo_flow_enabled() -> bool:
    return get_settings().APP_ENV in ("local", "development")


def format_demo_flow_result(result: DemoFlowResult) -> str:
    return (
        f"Перевірку завершено.\n"
        f"Заявка №{result.request_id} — внесено в графік відпусток."
    )


def _request_id_arg(text: str) -> str | None:
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        return None
    return parts[1].strip()


async def _run_commander_approve(
    telegram_user_id: int,
    request_id: str,
) -> tuple[str, object | None]:
    try:
        session_factory = await get_session_factory()
        async with session_factory() as auth_session:
            commander = await require_role(
                auth_session,
                telegram_user_id,
                {UserRole.COMMANDER.value},
            )
        async with session_factory() as session:
            updated = await approve_by_commander(
                session,
                request_id=request_id,
                commander_id=str(commander.id),
            )
            selected_leave_period = await _load_selected_leave_period(session, updated)
    except (RoleRequiredError, InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        return _friendly_access_error(exc), None
    except ValueError as exc:
        return await _friendly_commander_approve_error(request_id, exc), None
    except Exception:
        return "Не вдалося погодити заявку. Спробуйте пізніше.", None

    return format_request_status(updated, selected_leave_period), commander_menu_keyboard()


async def _run_mark_ready(
    telegram_user_id: int,
    request_id: str,
) -> tuple[str, object | None]:
    try:
        session_factory = await get_session_factory()
        async with session_factory() as auth_session:
            await require_role(
                auth_session,
                telegram_user_id,
                {UserRole.ADMIN.value},
            )
        async with session_factory() as session:
            updated = await mark_ready_to_apply(session, request_id=request_id)
            selected_leave_period = await _load_selected_leave_period(session, updated)
    except (RoleRequiredError, InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        return _friendly_access_error(exc), None
    except ValueError as exc:
        return await _friendly_mark_ready_error(request_id, exc), None
    except Exception:
        return "Не вдалося оновити заявку. Спробуйте пізніше.", None

    return format_request_status(updated, selected_leave_period), admin_menu_keyboard()


async def _run_mark_applied(
    telegram_user_id: int,
    request_id: str,
) -> tuple[str, object | None]:
    try:
        session_factory = await get_session_factory()
        async with session_factory() as auth_session:
            await require_role(
                auth_session,
                telegram_user_id,
                {UserRole.ADMIN.value},
            )
        async with session_factory() as session:
            updated = await mark_applied(session, request_id=request_id)
            selected_leave_period = await _load_selected_leave_period(session, updated)
    except (RoleRequiredError, InactivePersonnelError, TelegramPersonnelNotFoundError) as exc:
        return _friendly_access_error(exc), None
    except ValueError as exc:
        return await _friendly_mark_applied_error(request_id, exc), None
    except Exception:
        return "Не вдалося внести заявку в графік. Спробуйте пізніше.", None

    return format_request_status(updated, selected_leave_period), admin_menu_keyboard()


async def _load_selected_leave_period(
    session,
    request: LeaveRequest,
) -> LeavePeriod | None:
    if request.selected_leave_period_id is None:
        return None
    if session.in_transaction():
        return await session.get(LeavePeriod, request.selected_leave_period_id)
    async with session.begin():
        return await session.get(LeavePeriod, request.selected_leave_period_id)


async def _load_requests_by_status(
    session_factory,
    *,
    status: RequestStatus,
) -> tuple[tuple[LeaveRequest, LeavePeriod | None], ...]:
    async with session_factory() as session, session.begin():
        result = await session.execute(
            select(LeaveRequest)
            .where(LeaveRequest.status == status)
            .order_by(LeaveRequest.id)
            .limit(20)
        )
        requests = tuple(result.scalars())
        items: list[tuple[LeaveRequest, LeavePeriod | None]] = []
        for request in requests:
            leave_period = await _load_selected_leave_period(session, request)
            items.append((request, leave_period))
        return tuple(items)


async def _load_request_status(request_id: str) -> RequestStatus | None:
    try:
        request_pk = int(request_id)
    except ValueError:
        return None
    session_factory = await get_session_factory()
    async with session_factory() as session, session.begin():
        request = await session.get(LeaveRequest, request_pk)
        if request is None:
            return None
        return request.status


def _friendly_access_error(exc: Exception) -> str:
    if isinstance(exc, RoleRequiredError):
        return str(exc)
    return _friendly_personnel_error(exc)


def _friendly_personnel_error(exc: Exception) -> str:
    if isinstance(exc, InactivePersonnelError):
        return (
            "Ваш профіль Personnel неактивний. "
            "Заявки та команди погодження недоступні."
        )
    if isinstance(exc, TelegramPersonnelNotFoundError):
        return PERSONNEL_NOT_IN_DATABASE_MESSAGE
    return str(exc)


async def _friendly_pick_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "must be in options_generated" in message:
        status = await _load_request_status(request_id)
        if status == RequestStatus.SELECTED_BY_USER:
            return "Цю дію вже виконано."
        return "Заявка вже не очікує цієї дії."
    return await _generic_workflow_error(request_id, exc)


async def _friendly_submit_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "must be in selected_by_user" not in message:
        return await _generic_workflow_error(request_id, exc)

    status = await _load_request_status(request_id)
    if status is None:
        return f"Заявку №{request_id} не знайдено."
    if status == RequestStatus.WAITING_COMMANDER_APPROVAL:
        return (
            f"Заявка №{request_id} уже на погодженні.\n"
            f"Статус: {request_status_label(status)}"
        )
    if status in {
        RequestStatus.APPROVED_BY_COMMANDER,
        RequestStatus.READY_TO_APPLY,
        RequestStatus.APPLIED,
    }:
        return "Цю дію вже виконано."
    return (
        f"Заявка №{request_id} уже не очікує відправки на погодження.\n"
        f"Статус: {request_status_label(status)}"
    )


async def _friendly_commander_approve_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "was not found" in message:
        return f"Заявку №{request_id} не знайдено."
    if "must be in waiting_commander_approval" in message:
        status = await _load_request_status(request_id)
        if status == RequestStatus.APPROVED_BY_COMMANDER:
            return "Цю дію вже виконано."
        if status == RequestStatus.APPLIED:
            return "Заявку вже внесено в графік."
        return "Заявка вже не очікує цієї дії."
    return await _generic_workflow_error(request_id, exc)


async def _friendly_mark_ready_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "was not found" in message:
        return f"Заявку №{request_id} не знайдено."
    if "must be in approved_by_commander" in message:
        status = await _load_request_status(request_id)
        if status == RequestStatus.READY_TO_APPLY:
            return "Цю дію вже виконано."
        if status == RequestStatus.APPLIED:
            return "Заявку вже внесено в графік."
        return "Заявка вже не очікує цієї дії."
    return await _generic_workflow_error(request_id, exc)


async def _friendly_mark_applied_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "was not found" in message:
        return f"Заявку №{request_id} не знайдено."
    if "must be in ready_to_apply" in message:
        status = await _load_request_status(request_id)
        if status == RequestStatus.APPLIED:
            return "Заявку вже внесено в графік."
        return "Заявка вже не очікує цієї дії."
    return await _generic_workflow_error(request_id, exc)


async def _generic_workflow_error(request_id: str, exc: ValueError) -> str:
    message = str(exc)
    if "was not found" in message:
        return f"Заявку №{request_id} не знайдено."
    if "Invalid request_id" in message:
        return "Некоректний номер заявки."
    if "must be in" in message:
        return "Заявка вже не очікує цієї дії."
    return f"Не вдалося обробити заявку №{request_id}."
