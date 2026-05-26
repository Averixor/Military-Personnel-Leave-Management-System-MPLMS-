# Military Personnel Leave Management System

MPLMS — enterprise-level workflow platform для управления отпусками военнослужащих.

Telegram в этой системе является только пользовательским интерфейсом. Бизнес-логика, планирование, согласования, юридические правила, внутренние политики, аудит и восстановление живут в отдельных модулях.

## Главная цель

Создать устойчивую систему кадрового планирования отпусков, которая:

- сохраняет боеспособность подразделения;
- минимизирует конфликты дат;
- поддерживает военную иерархию согласований;
- ведет неизменяемый аудит решений;
- позволяет пересчитывать графики без потери истории;
- масштабируется до 1000+ военнослужащих;
- поддерживает эволюцию правил через версионирование политик.

## Ключевой принцип планирования

Система не ищет идеальный график.

Планирование отпусков с большим количеством ограничений является CSP-like / resource-constrained scheduling problem. Поэтому Scheduler Engine должен искать допустимый и стабильный график с помощью эвристик, локального поиска, conflict scoring и timeout-based execution.

## Основные модули

- Telegram Bot Layer
- Scheduler Engine
- Approval Workflow Engine
- Legal Rules Engine
- Internal Policy Engine
- Notification Engine
- Audit & Snapshot System
- Background Jobs
- RBAC & Security Layer

## Стартовая документация

- [Архитектура](docs/ARCHITECTURE.md)
- [Доменная модель](docs/DOMAIN_MODEL.md)
- [Scheduler Engine](docs/SCHEDULER_ENGINE.md)
- [Workflow заявок](docs/APPROVAL_WORKFLOW.md)
- [Roadmap реализации](docs/ROADMAP.md)
- [Разработка без Docker](docs/LOCAL_DEV_NO_DOCKER.md)

## Технологический стек

- Python 3.12+
- PostgreSQL
- SQLAlchemy 2
- Alembic
- aiogram 3
- APScheduler для MVP background jobs
- Docker / Docker Compose

**Production** использует PostgreSQL. **Локальная разработка** по умолчанию — SQLite (без Docker и без установки PostgreSQL). Google Sheets не используется.

## Локальный запуск (без Docker)

См. [docs/LOCAL_DEV_NO_DOCKER.md](docs/LOCAL_DEV_NO_DOCKER.md).

```powershell
uv sync --extra dev
Copy-Item .env.example .env   # DATABASE_URL можно не задавать
uv run alembic upgrade head
uv run python -m mplms.main
uv run pytest -ra
```

## PostgreSQL (optional, Docker)

```powershell
cd infra/docker
docker compose up -d postgres
cd ../..
$env:DATABASE_URL = "postgresql+asyncpg://mplms:mplms@localhost:5432/mplms"
uv run alembic upgrade head
uv run python -m mplms.main
```

См. [infra/docker/README.md](infra/docker/README.md).

## Текущий статус реализации

Заложен backend scaffold:

- конфигурация Python-проекта;
- Docker Compose с PostgreSQL;
- Alembic;
- SQLAlchemy-модели основных сущностей;
- доменные enum;
- FSM transition guard;
- road-days policy;
- начальная граница Scheduler Engine.
