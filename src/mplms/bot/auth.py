"""Tiny RBAC helpers for Telegram MVP commands."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mplms.bot.database import ensure_personnel_in_session
from mplms.domain.enums import UserRole
from mplms.models.personnel import Personnel


class RoleRequiredError(PermissionError):
    def __init__(self, actual_role: str, allowed_roles: set[str]) -> None:
        self.actual_role = actual_role
        self.allowed_roles = allowed_roles
        super().__init__(role_required_message(allowed_roles))


def role_required_message(allowed_roles: set[str]) -> str:
    if allowed_roles == {UserRole.COMMANDER.value}:
        return "Ця дія доступна лише командиру."
    if allowed_roles == {UserRole.ADMIN.value}:
        return "Ця дія доступна лише адміністратору."
    return "У вас немає прав для цієї дії."


async def require_role(
    session: AsyncSession,
    telegram_id: int,
    allowed_roles: set[str],
) -> Personnel:
    """Return Telegram-linked personnel if its role is allowed.

    This is MVP RBAC, not production auth. Unknown Telegram users are created as
    regular personnel so read/self-service commands can proceed in dev SQLite.
    """

    async with session.begin():
        person = await ensure_personnel_in_session(
            session,
            telegram_user_id=telegram_id,
            display_name=None,
            require_active=True,
        )
        role = str(getattr(person.role, "value", person.role))
        if role not in allowed_roles:
            raise RoleRequiredError(role, allowed_roles)
        return person
