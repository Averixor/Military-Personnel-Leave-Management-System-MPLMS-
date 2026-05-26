# Approval Workflow

## Главный принцип

Автоматическое применение изменений запрещено.

Даже после всех согласований финальное применение выполняет только администратор.

## FSM статусы заявки

- draft;
- options_generated;
- selected_by_user;
- waiting_affected_people;
- waiting_admin_review;
- waiting_commander_approval;
- approved_by_commander;
- ready_to_apply;
- applied;
- rejected;
- expired;
- cancelled;
- manual_admin_review_required.

## Типовой сценарий

1. Пользователь создает заявку.
2. Указывает дату, место, дни дороги и документы.
3. Scheduler Engine генерирует 3-10 вариантов.
4. Пользователь выбирает вариант.

## Approval Persistence (MVP)

DB-backed переходы (`approval_persistence.py`):

1. `submit_selected_request_for_approval` — `selected_by_user` → `waiting_commander_approval`
2. `approve_by_commander` — `waiting_commander_approval` → `approved_by_commander` (+ `ApprovalStep`)
3. `mark_ready_to_apply` — `approved_by_commander` → `ready_to_apply`
4. `mark_applied` — `ready_to_apply` → `applied` (требует `selected_leave_period_id`)

Полный flow: create request → select option → submit approval → commander approve → ready_to_apply → applied.

## MVP сервисный слой (без БД)

```python
from mplms.services.leave_request import create_leave_request_draft, select_leave_option

draft = create_leave_request_draft(
    personnel_id="42",
    desired_start=date(2026, 6, 15),
    duration_days=15,
    leave_type="annual_main",
    existing_periods=[],
)
# draft.status == "options_generated"

draft = select_leave_option(draft, option_index=0)
# draft.status == "selected_by_user"
```

Если Scheduler не нашёл допустимых вариантов, `create_leave_request_draft` возвращает
`status="manual_review_required"` и пустой список `options`. 5. Если затрагиваются другие люди, система запрашивает их согласие. 6. После согласий заявка идет администратору. 7. Администратор проверяет и отправляет командиру. 8. Командир утверждает или отклоняет. 9. При отсутствии командира используется заместитель. 10. После утверждения заявка становится ready_to_apply. 11. Администратор применяет изменения.

## Невалидные переходы

Запрещены:

- draft -> applied;
- options_generated -> applied;
- selected_by_user -> approved_by_commander;
- waiting_affected_people -> waiting_commander_approval без всех согласий;
- rejected -> applied;
- expired -> applied;
- cancelled -> applied;
- applied -> любой другой статус.

## Expiration Logic

Заявка может истечь, если:

- пользователь не выбрал вариант;
- affected people не ответили в срок;
- admin review не выполнен в срок;
- commander approval не выполнен в срок.

Истечение фиксируется в audit log.

## Commander Deputy Routing

Если командир отсутствует или недоступен, Approval Workflow Engine должен определить заместителя по:

- unit structure;
- delegation table;
- active leave status;
- role permissions.

Решение о маршрутизации фиксируется в audit.

## Override

### Soft Override

Admin может:

- вручную отклонить;
- отправить на manual review;
- назначить priority;
- включить emergency routing.

### Hard Override

Только super admin может:

- unfreeze;
- force apply;
- exceed limits;
- modify criticality;
- restore snapshots.

Любой override обязан иметь reason и audit event.
