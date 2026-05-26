"""Telegram reply and inline keyboards (thin UI)."""

from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import KeyboardButton
from aiogram.types import ReplyKeyboardMarkup

from mplms.bot.leave_request_ui import MAX_OPTIONS_TO_SHOW
from mplms.bot.session import ADMIN_MARK_APPLIED_PREFIX
from mplms.bot.session import ADMIN_MARK_READY_PREFIX
from mplms.bot.session import COMMANDER_APPROVE_PREFIX
from mplms.bot.session import LEAVE_PICK_PREFIX
from mplms.bot.session import SUBMIT_APPROVAL_CALLBACK

BTN_SUBMIT_LEAVE = "Подати заявку на відпустку"
BTN_MY_REQUESTS = "Мої заявки"
BTN_HELP = "Допомога"
BTN_COMMANDER_PENDING = "Заявки на погодження"
BTN_ADMIN_ACTIONS = "Адмін-дії"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SUBMIT_LEAVE)],
            [KeyboardButton(text=BTN_MY_REQUESTS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def commander_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_COMMANDER_PENDING)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def admin_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ADMIN_ACTIONS)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def leave_option_keyboard(option_count: int) -> InlineKeyboardMarkup:
    count = min(option_count, MAX_OPTIONS_TO_SHOW)
    rows = [
        [
            InlineKeyboardButton(
                text=f"Обрати варіант {index + 1}",
                callback_data=f"{LEAVE_PICK_PREFIX}{index}",
            )
        ]
        for index in range(count)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def approval_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подати на погодження",
                    callback_data=SUBMIT_APPROVAL_CALLBACK,
                )
            ]
        ]
    )


def commander_pending_keyboard(request_ids: tuple[str, ...]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"Погодити №{request_id}",
                callback_data=f"{COMMANDER_APPROVE_PREFIX}{request_id}",
            )
        ]
        for request_id in request_ids
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_actions_keyboard(
    *,
    approved_ids: tuple[str, ...],
    ready_ids: tuple[str, ...],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for request_id in approved_ids:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Позначити готовою №{request_id}",
                    callback_data=f"{ADMIN_MARK_READY_PREFIX}{request_id}",
                )
            ]
        )
    for request_id in ready_ids:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"Внести в графік №{request_id}",
                    callback_data=f"{ADMIN_MARK_APPLIED_PREFIX}{request_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
