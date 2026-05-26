# Developer Specification

Версия: 1.0

Статус: Architecture & Development Specification

Целевая аудитория:

- backend developers;
- system architects;
- DevOps engineers;
- fullstack developers.

## Must Have

- PostgreSQL как production-хранилище; SQLite (`aiosqlite`) для локальной разработки по умолчанию.
- SQLAlchemy 2 + Alembic.
- Telegram bot как тонкий UI-слой.
- Scheduler Engine без зависимости от Telegram.
- Workflow Engine с жесткой FSM-валидацией.
- Legal Rules Engine и Internal Policy Engine отдельно от workflow.
- Immutable audit logs.
- PostgreSQL transactions для критических операций.
- Row locking перед применением изменений.
- Snapshots перед массовыми изменениями и nightly replan.
- PolicySnapshot для версионирования правил.

## Must Not Have

- Бизнес-логика в Telegram handlers.
- SQLite как production database (только dev/test default).
- Google Sheets как production database.
- Автоматическое применение заявки после approval.
- Прямой обход FSM.
- Double apply.
- Удаление audit logs.
- Self-overlapping leave у одного человека.
- Изменение frozen leave без hard override.

## Performance Targets

- Single request scheduling: target < 1 second.
- Nightly replan: 30-60 seconds timeout.
- Supported scale: 1000+ personnel.

## Required Background Jobs

- freeze_leaves_20_days;
- remind_approvals;
- expire_requests;
- nightly_replan;
- generate_future_leaves;
- snapshot_schedule.
