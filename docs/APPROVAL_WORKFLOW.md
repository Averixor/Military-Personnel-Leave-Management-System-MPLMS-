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
5. Если затрагиваются другие люди, система запрашивает их согласие.
6. После согласий заявка идет администратору.
7. Администратор проверяет и отправляет командиру.
8. Командир утверждает или отклоняет.
9. При отсутствии командира используется заместитель.
10. После утверждения заявка становится ready_to_apply.
11. Администратор применяет изменения.

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

