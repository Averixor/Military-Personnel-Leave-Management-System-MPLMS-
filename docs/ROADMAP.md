# Roadmap реализации

## Phase 0 — Project Foundation

Цель: зафиксировать архитектурный контракт и границы модулей.

Результат:

- README;
- архитектурная документация;
- доменная модель;
- описание Scheduler Engine;
- описание Approval Workflow.

## Phase 1 — Backend Core

Цель: поднять минимальное backend-ядро без Telegram.

Компоненты:

- PostgreSQL schema;
- migrations;
- Personnel model;
- Leave model;
- Leave Request model;
- Policy Version model;
- Audit Event model;
- базовый RBAC.

## Phase 2 — Rules Engines

Цель: отделить правила от workflow.

Компоненты:

- Legal Rules Engine;
- Internal Policy Engine;
- policy versioning;
- annual leave validation;
- road days calculation;
- freeze period calculation;
- overlap policy checks.

## Phase 3 — Scheduler MVP

Цель: реализовать первый find_acceptable_slots.

Компоненты:

- candidate window generation;
- frozen leave exclusion;
- self-overlap check;
- hierarchy restriction check;
- overlap limits;
- +/-2 rule;
- conflict_score;
- ranked options.

## Phase 4 — Approval Workflow MVP

Цель: реализовать FSM заявок.

Компоненты:

- allowed transitions;
- selected option flow;
- affected people consent;
- admin review;
- commander approval;
- ready_to_apply;
- transactional apply;
- expiration.

## Phase 5 — Telegram Bot Layer

Цель: подключить Telegram как UI.

Компоненты:

- auth by telegram_id;
- create request flow;
- option selection;
- consent buttons;
- admin panel commands;
- commander approval commands;
- notifications.

## Phase 6 — Background Jobs

Цель: автоматизировать обслуживание системы.

Компоненты:

- freeze jobs;
- reminder jobs;
- expiration jobs;
- snapshot generation;
- future leave generation;
- nightly replan.

## Phase 7 — Recovery & Operations

Цель: подготовить систему к эксплуатации.

Компоненты:

- backup;
- restore;
- snapshot retention;
- rollback tooling;
- audit review;
- operational dashboards;
- incident playbooks.

## Phase 8 — Scale & Hardening

Цель: выдерживать 1000+ personnel.

Компоненты:

- indexes;
- query optimization;
- read models;
- load testing;
- scheduler timeout tuning;
- queue hardening;
- permission audit.

