# Архитектура MPLMS

## 1. Архитектурная позиция

MPLMS проектируется как распределенная кадровая workflow-платформа, а не как Telegram-бот.

Telegram Bot Layer не должен содержать бизнес-логику. Его задача — принимать команды, показывать кнопки, вести диалоги, отправлять уведомления и отображать состояние системы.

Все критические решения принимаются отдельными доменными сервисами.

## 1.1 Технологический контракт

Backend:

- Python 3.12+;
- SQLAlchemy 2;
- Alembic;
- PostgreSQL;
- aiogram 3 для Telegram UI;
- APScheduler для MVP background jobs;
- Docker Compose для локальной инфраструктуры.

Архитектура должна позволять заменить APScheduler на Celery + Redis без переписывания доменной логики.

## 2. Модули системы

### Telegram Bot Layer

Отвечает за:

- команды;
- inline-кнопки;
- диалоги;
- уведомления;
- подачу заявок;
- отображение графиков и статусов.

Не отвечает за:

- расчет отпусков;
- проверку ограничений;
- принятие решений;
- изменение графика напрямую.

### Scheduler Engine

Ядро планирования.

Отвечает за:

- подбор допустимых дат;
- проверку frozen leaves;
- проверку overlap limits;
- проверку hierarchy restrictions;
- проверку правила +/-2 дня;
- conflict scoring;
- nightly replan;
- генерацию будущих отпусков.

### Approval Workflow Engine

Отвечает за жизненный цикл заявки:

- конечный автомат статусов;
- цепочки согласований;
- согласие затронутых людей;
- admin review;
- commander approval;
- deputy routing;
- expiration logic;
- запрет невалидных переходов.

### Legal Rules Engine

Изолирует законодательные нормы от бизнес-логики:

- типы отпусков;
- основной отпуск;
- дни дороги;
- УБД;
- семейные отпуска;
- медицинские отпуска;
- отпуска после плена;
- версии правовых норм.

### Internal Policy Engine

Содержит внутренние правила подразделения:

- freeze periods;
- overlap limits;
- hierarchy restrictions;
- criticality limits;
- staffing rules;
- +/-2 rules;
- версии внутренних политик.

### Notification Engine

Отвечает за:

- Telegram notifications;
- reminders;
- escalation alerts;
- freeze warnings;
- offline recovery queue.

### Audit & Snapshot System

Отвечает за:

- immutable audit log;
- override logging;
- snapshots;
- rollback;
- history tracking;
- disaster recovery.

## 3. Транзакционная модель

Все критические операции выполняются внутри PostgreSQL transactions.

Критическими считаются:

- применение утвержденной заявки;
- изменение графика;
- freeze / unfreeze;
- override;
- snapshot restore;
- nightly replan commit;
- изменение статуса заявки;
- назначение согласующих лиц.

Используются:

- row locking;
- `SELECT FOR UPDATE`;
- optimistic version checks;
- rollback on failure;
- idempotency keys для повторных операций.

## 4. Инварианты системы

Нельзя нарушать ни при каких условиях:

- нельзя ломать FSM заявки;
- нельзя применять одну заявку дважды;
- нельзя создавать self-overlap у одного человека;
- нельзя удалять audit records;
- нельзя обходить транзакции;
- нельзя автоматически двигать frozen leave;
- нельзя применять изменения без финального admin apply;
- нельзя менять прошлые решения без audit entry.

## 5. Масштабирование

Целевая нагрузка: 1000+ personnel без изменения архитектуры.

Основной подход:

- PostgreSQL как источник истины;
- отдельные background jobs;
- индексы по датам, person_id, unit_id, status;
- snapshot-based replanning;
- timeout-safe scheduler;
- кэширование read models для Telegram UI.
