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

## Leave Request Persistence (MVP)

`create_persisted_leave_request` загружает `LeavePeriod` из БД, вызывает `create_leave_request_draft`,
сохраняет `LeaveRequest` и возвращает DTO с `options` (без отдельного сохранения options в БД).

`select_persisted_leave_option` создаёт `LeavePeriod` по выбранному `ScheduleOption`,
связывает через `source_request_id`, заполняет `selected_leave_period_id` и переводит заявку в `selected_by_user`.

## Approval Workflow Persistence (MVP)

`submit_selected_request_for_approval`, `approve_by_commander`, `mark_ready_to_apply`, `mark_applied`
в `approval_persistence.py` — FSM через `workflow.transition`, утверждение командира в `approval_steps`.

## Audit (MVP)

`create_audit_log` в `audit.py` пишет в `audit_logs` (`action`, `before_state`, `after_state`, `actor_id`).
Persistence-слои логируют: `leave_request_created`, `leave_option_selected`, `submitted_for_approval`,
`commander_approved`, `ready_to_apply`, `applied`.

## Required Background Jobs

- freeze_leaves_20_days;
- remind_approvals;
- expire_requests;
- nightly_replan;
- generate_future_leaves;
- snapshot_schedule.
