# Локальная разработка без Docker и PostgreSQL

MPLMS поддерживает два режима базы данных:

| Режим                  | `DATABASE_URL`             | Когда использовать                         |
| ---------------------- | -------------------------- | ------------------------------------------ |
| **DEV (по умолчанию)** | не задан или SQLite        | Локальная разработка, тесты, быстрый старт |
| **PROD / staging**     | `postgresql+asyncpg://...` | Docker Compose, VPS, CI с PostgreSQL       |

Если переменная `DATABASE_URL` **не задана** (или пустая), приложение использует:

```text
sqlite+aiosqlite:///./data/mplms_dev.sqlite3
```

Папка `data/` создаётся автоматически при импорте `mplms.core.db` или запуске `python -m mplms.main`.

## Быстрый старт (Windows PowerShell)

```powershell
cd "C:\Users\User\Desktop\Military Personnel Leave Management System"

uv sync --extra dev
Copy-Item .env.example .env   # опционально; для SQLite DATABASE_URL можно не указывать

uv run alembic upgrade head
uv run python -m mplms.main

uv run pytest -ra
```

## Telegram Bot (MVP)

Тонкий UI-слой поверх backend. Бизнес-логика — в сервисах и `mplms.cli.run_demo_flow`.
DEV-режим использует SQLite по умолчанию; Docker/PostgreSQL для локального MVP не нужны.

```powershell
# В .env задайте токен от @BotFather:
# TELEGRAM_BOT_TOKEN=123456:ABC...

uv run python -m mplms.bot.main
```

Если `TELEGRAM_BOT_TOKEN` не задан, процесс завершится с сообщением:
`TELEGRAM_BOT_TOKEN is not configured.` (без падения с непонятной ошибкой).

Інтерфейс бота — **українською**, основні дії через кнопки (внутрішні статуси користувачу не показуються).

Головне меню (reply-кнопки):

- **Подати заявку на відпустку** — створити заявку, обрати один із 3 варіантів inline-кнопкою, потім «Подати на погодження»
- **Мої заявки** — список ваших заявок зі зрозумілими статусами
- **Допомога** — довідка

Для командира:

- **Заявки на погодження** (або `/commander_pending`) — список заявок з кнопкою «Погодити» під кожною

Для адміністратора:

- **Адмін-дії** (або `/admin_actions`) — заявки після погодження командиром; кнопки «Позначити готовою» / «Внести в графік»

Резервні команди (fallback):

- `/start`, `/help`, `/request_leave`, `/my_request`, `/my_requests`
- `/cancel_request [номер]` — скасувати заявку до внесення в графік
- `/commander_approve [номер]`, `/mark_ready [номер]`, `/mark_applied [номер]`
- `/demo_flow` — технічний demo-flow (як CLI)

Bot RBAC MVP навмисно простий: роль береться з `personnel.role` за `telegram_id`.
Нові Telegram-користувачі в dev SQLite можуть автоматично створюватися як `personnel`;
demo commander/admin створюються окремими dev helpers і не обходять перевірку ролей.

## Ручной прогон полного flow (CLI)

Без Docker, PostgreSQL и Telegram — на dev SQLite:

```powershell
uv run python -m mplms.cli demo-flow
```

Команда створює `./data/mplms_dev.sqlite3` (якщо немає), піднімає таблиці, додає demo-персонал,
проганяє повний workflow заявки та друкує технічний audit trail.

Для отдельного файла БД:

```powershell
uv run python -m mplms.cli demo-flow --database-url "sqlite+aiosqlite:///./data/mplms_cli_demo.sqlite3"
```

## Импорт личного состава из CSV

Формат CSV:

```text
personnel_code,full_name,rank,position,role,telegram_id,is_active
```

Поддерживаемые роли: `personnel`, `commander`, `admin`.
`telegram_id` можно оставить пустым. `is_active` по умолчанию `true`; также принимаются
`true/1/yes/так/да` и `false/0/no/ні/нет`.

Пример локального импорта в dev SQLite:

```powershell
uv run python -m mplms.cli import-personnel examples/personnel_sample.csv
uv run python -m mplms.bot.main
```

Повторный импорт строки с тем же `personnel_code` обновляет существующую запись.
Ошибки отдельных строк выводятся в summary и не останавливают весь импорт.
После импорта бот сначала ищет пользователя по `telegram_id` в таблице `personnel` и берёт оттуда
`role` и `is_active`. Так Telegram-пользователь из CSV сразу получает права `personnel`,
`commander` или `admin`.

Для dev/demo режима доступно автосоздание неизвестных Telegram-пользователей:

```env
BOT_AUTO_CREATE_PERSONNEL=true
```

По умолчанию оно включено. Если установить `BOT_AUTO_CREATE_PERSONNEL=false`, неизвестный
`telegram_id` будет отклонён до импорта/привязки Personnel.

## Проверка сборки

```powershell
uv sync --extra dev
uv run python -m compileall src tests migrations
uv run pytest -ra
```

Ожидается зелёный прогон всего набора `tests/` (SQLite in-memory).

## Миграции Alembic

```powershell
# SQLite (dev) — URL из настроек по умолчанию
uv run alembic upgrade head

# PostgreSQL (optional Docker in infra/docker/)
$env:DATABASE_URL = "postgresql+asyncpg://mplms:mplms@localhost:5432/mplms"
docker compose -f infra/docker/docker-compose.yml up -d postgres
uv run alembic upgrade head
```

## Переключение на PostgreSQL

В `.env`:

```env
DATABASE_URL=postgresql+asyncpg://mplms:mplms@localhost:5432/mplms
```

Зависимости `asyncpg` и `psycopg` остаются в проекте — PostgreSQL не удалён.

## Ограничения SQLite в DEV

- Предназначен для разработки и unit/integration-тестов, не для production.
- Некоторые операции PostgreSQL (расширенный locking, JSONB-специфика) в DEV не используются — модели используют переносимый тип `JSON`.
- Для нагрузочного тестирования и nightly replan используйте PostgreSQL.

## Файлы данных

- `data/mplms_dev.sqlite3` — локальная БД (в `.gitignore`)
- Не коммитьте `.env` с секретами
