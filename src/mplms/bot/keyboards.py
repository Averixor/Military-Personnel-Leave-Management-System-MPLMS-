"""Telegram reply keyboards (thin UI)."""

from aiogram.types import KeyboardButton
from aiogram.types import ReplyKeyboardMarkup

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
