import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.users.models import User
from app.features.users.schemas import UpdateProfileRequest


class UserError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


async def get_me(user_id: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise UserError("User not found", status_code=404)
    return user


async def update_profile(user_id: str, data: UpdateProfileRequest, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise UserError("User not found", status_code=404)

    if data.display_name is not None:
        user.display_name = data.display_name
    if data.status_text is not None:
        user.status_text = data.status_text

    await db.commit()
    await db.refresh(user)
    return user


async def update_avatar(user_id: str, avatar_url: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise UserError("User not found", status_code=404)

    user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return user


async def search_by_username(username: str, searcher_id: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)  # noqa
    )
    user = result.scalar_one_or_none()
    if not user:
        return None

    # Проверяем не заблокировал ли найденный пользователь ищущего
    from app.features.contacts.service import is_blocked
    if await is_blocked(str(user.id), searcher_id, db):
        return None

    return user

async def get_public_profile(user_id: str, db: AsyncSession) -> User | None:
    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise UserError("User not found", 404)
    return user
