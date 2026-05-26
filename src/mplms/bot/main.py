"""Telegram bot entrypoint (thin UI over backend services)."""

from __future__ import annotations

import asyncio
import sys

from aiogram import Bot
from aiogram import Dispatcher

from mplms.bot.handlers import router
from mplms.core.config import get_settings

NOT_CONFIGURED_MESSAGE = "TELEGRAM_BOT_TOKEN is not configured."


def resolve_telegram_token() -> str | None:
    return get_settings().bot_token_value


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    return dispatcher


async def run_polling(token: str) -> None:
    bot = Bot(token=token)
    dispatcher = create_dispatcher()
    await dispatcher.start_polling(bot)


def main() -> int:
    token = resolve_telegram_token()
    if not token:
        print(NOT_CONFIGURED_MESSAGE)
        return 1

    try:
        asyncio.run(run_polling(token))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
