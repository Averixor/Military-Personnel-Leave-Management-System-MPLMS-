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

## Технологический стек

- Python 3.12+
- PostgreSQL
- SQLAlchemy 2
- Alembic
- aiogram 3
- APScheduler для MVP background jobs
- Docker / Docker Compose

SQLite и Google Sheets не используются как основное хранилище.

## Локальный запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d postgres
python -m mplms.main
```

Для Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d postgres
python -m mplms.main
```

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
