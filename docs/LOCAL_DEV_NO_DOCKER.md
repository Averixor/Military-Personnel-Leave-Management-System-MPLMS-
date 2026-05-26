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

## Telegram Bot (MVP skeleton)

Тонкий UI-слой поверх backend. Бизнес-логика — в сервисах и `mplms.cli.run_demo_flow`.

```powershell
# В .env задайте токен от @BotFather:
# TELEGRAM_BOT_TOKEN=123456:ABC...

uv run python -m mplms.bot.main
```

Если `TELEGRAM_BOT_TOKEN` не задан, процесс завершится с сообщением:
`TELEGRAM_BOT_TOKEN is not configured.` (без падения с непонятной ошибкой).

Команды бота: `/start`, `/help`, `/demo_flow` (тот же flow, что CLI `demo-flow`).

## Ручной прогон полного flow (CLI)

Без Docker, PostgreSQL и Telegram — на dev SQLite:

```powershell
uv run python -m mplms.cli demo-flow
```

Команда создаёт `./data/mplms_dev.sqlite3` (если нет), поднимает таблицы, сидирует demo-персонал,
прогоняет: create request → select option → submit → commander approve → ready_to_apply → applied,
и печатает финальный статус и audit trail.

Для отдельного файла БД:

```powershell
uv run python -m mplms.cli demo-flow --database-url "sqlite+aiosqlite:///./data/mplms_cli_demo.sqlite3"
```

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
