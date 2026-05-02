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


async def search_by_username(username: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).where(User.username == username, User.is_active == True)  # noqa
    )
    return result.scalar_one_or_none()

async def get_public_profile(user_id: str, db: AsyncSession) -> User | None:
    user = await db.get(User, uuid.UUID(user_id))
    if not user:
        raise UserError("User not found", 404)
    return user
