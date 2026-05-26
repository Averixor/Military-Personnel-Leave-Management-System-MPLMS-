# Доменная модель

## Personnel

Военнослужащий.

Ключевые поля:

- id;
- telegram_id;
- full_name;
- rank;
- unit_id;
- role;
- commander_id;
- deputy_id;
- criticality_level;
- is_active;
- created_at;
- updated_at.

## Criticality Level

- 0 — обычный;
- 1 — важный;
- 2 — критический;
- 3 — стратегический.

Влияет на:

- freeze period;
- conflict score;
- overlap limits;
- scheduling priority;
- допустимость одновременного отсутствия.

## Leave

Фактический или запланированный отпуск.

Ключевые поля:

- id;
- person_id;
- leave_type;
- year;
- starts_on;
- ends_on;
- days_count;
- initial_starts_on;
- initial_ends_on;
- status;
- is_frozen;
- frozen_at;
- policy_version_id;
- source_request_id;
- created_at;
- updated_at.

## Leave Type

Минимальные типы:

- annual_main;
- annual_second_part;
- road_days;
- medical;
- family;
- combatant;
- post_captivity;
- other_special.

## Road Days

Дни дороги являются отдельной сущностью.

Они:

- не входят в отпуск;
- не участвуют в conflict scoring как отпуск;
- не участвуют в overlap limits;
- увеличивают только фактическое отсутствие;
- выбираются человеком добровольно в пределах допустимого лимита.

Правила:

- до 200 км — 0 дней;
- 200-800 км — 2 дня;
- 800+ км — 4 дня;
- для заграницы учитывается только украинская часть маршрута.

## Leave Request

Заявка на отпуск или изменение отпуска.

Ключевые поля:

- id;
- person_id;
- desired_start_date;
- desired_days_count;
- destination_locality;
- requested_road_days;
- attached_documents;
- status;
- policy_version_id;
- selected_option_id;
- expires_at;
- created_at;
- updated_at.

## Request Option

Вариант, сгенерированный Scheduler Engine.

Ключевые поля:

- id;
- request_id;
- proposed_start_date;
- proposed_end_date;
- conflict_score;
- overlap_level;
- risk_level;
- affected_people_count;
- explanation;
- is_selectable.

## Affected Person Consent

Согласие человека, чей отпуск может быть затронут.

Ключевые поля:

- id;
- request_id;
- affected_person_id;
- affected_leave_id;
- proposed_shift_days;
- status;
- responded_at;
- expires_at.

Статусы:

- pending;
- accepted;
- rejected;
- expired.

## Policy Version

Версия правил.

Ключевые поля:

- id;
- legal_rules_version;
- internal_policy_version;
- effective_from;
- effective_to;
- is_active;
- created_by;
- created_at.

Каждая заявка хранит policy_version_id. Старые заявки продолжают жить по старым правилам.

## Audit Event

Неизменяемая запись аудита.

Ключевые поля:

- id;
- actor_id;
- actor_role;
- action;
- entity_type;
- entity_id;
- before_state;
- after_state;
- reason;
- created_at.

## Snapshot

Снимок состояния перед критическими операциями.

Используется для:

- nightly replan;
- disaster recovery;
- rollback;
- forensic analysis.

