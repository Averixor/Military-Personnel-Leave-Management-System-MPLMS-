"""Telegram reply and inline keyboards (thin UI)."""

from aiogram.types import InlineKeyboardButton
from aiogram.types import InlineKeyboardMarkup
from aiogram.types import KeyboardButton
from aiogram.types import ReplyKeyboardMarkup

from mplms.bot.leave_request_ui import MAX_OPTIONS_TO_SHOW
from mplms.bot.session import LEAVE_PICK_PREFIX

BTN_DEMO_REQUEST = "Создать демо-заявку"
BTN_HELP = "Помощь"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_DEMO_REQUEST)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
    )


def leave_option_keyboard(option_count: int) -> InlineKeyboardMarkup:
    count = min(option_count, MAX_OPTIONS_TO_SHOW)
    rows = [
        [
            InlineKeyboardButton(
                text=f"Выбрать вариант {index + 1}",
                callback_data=f"{LEAVE_PICK_PREFIX}{index}",
            )
        ]
        for index in range(count)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
