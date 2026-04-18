import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.chats.models import Chat, ChatMember
from app.features.chats.schemas import CreateChatRequest, UpdateChatRequest
from app.features.users.models import User


class ChatError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


async def get_user_chats(user_id: str, db: AsyncSession) -> list[Chat]:
    result = await db.execute(
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .where(ChatMember.user_id == uuid.UUID(user_id))
        .options(
            selectinload(Chat.members).selectinload(ChatMember.user)
        )
    )
    return list(result.scalars().all())


async def get_chat(chat_id: str, user_id: str, db: AsyncSession) -> Chat:
    result = await db.execute(
        select(Chat)
        .where(Chat.id == uuid.UUID(chat_id))
        .options(selectinload(Chat.members).selectinload(ChatMember.user))
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise ChatError("Chat not found", status_code=404)

    if not any(str(m.user_id) == user_id for m in chat.members):
        raise ChatError("Access denied", status_code=403)

    return chat


async def create_chat(data: CreateChatRequest, user_id: str, db: AsyncSession) -> Chat:
    if data.type not in ("direct", "group"):
        raise ChatError("Invalid chat type")

    if data.type == "direct":
        if len(data.member_ids) != 1:
            raise ChatError("Direct chat requires exactly 1 other member")

        other_id = data.member_ids[0]

        existing = await db.execute(
            select(Chat)
            .join(ChatMember, ChatMember.chat_id == Chat.id)
            .where(Chat.type == "direct", ChatMember.user_id == uuid.UUID(user_id))
            .options(selectinload(Chat.members).selectinload(ChatMember.user))
        )
        for chat in existing.scalars().all():
            ids = {str(m.user_id) for m in chat.members}
            if str(other_id) in ids and user_id in ids:
                return chat

    chat = Chat(
        type=data.type,
        name=data.name,
        created_by=uuid.UUID(user_id),
    )
    db.add(chat)
    await db.flush()

    members = [ChatMember(chat_id=chat.id, user_id=uuid.UUID(user_id), role="owner")]

    for member_id in data.member_ids:
        if str(member_id) != user_id:
            result = await db.execute(select(User).where(User.id == member_id))
            if not result.scalar_one_or_none():
                raise ChatError(f"User {member_id} not found", status_code=404)
            members.append(ChatMember(chat_id=chat.id, user_id=member_id, role="member"))

    db.add_all(members)
    await db.commit()

    result = await db.execute(
        select(Chat)
        .where(Chat.id == chat.id)
        .options(selectinload(Chat.members).selectinload(ChatMember.user))
    )
    return result.scalar_one()


async def update_chat(chat_id: str, user_id: str, data: UpdateChatRequest, db: AsyncSession) -> Chat:
    chat = await get_chat(chat_id, user_id, db)

    member = next((m for m in chat.members if str(m.user_id) == user_id), None)
    if not member or member.role not in ("owner", "admin"):
        raise ChatError("Not enough permissions", status_code=403)

    if data.name is not None:
        chat.name = data.name

    await db.commit()
    await db.refresh(chat)

    result = await db.execute(
        select(Chat)
        .where(Chat.id == chat.id)
        .options(selectinload(Chat.members).selectinload(ChatMember.user))
    )
    return result.scalar_one()


async def leave_chat(chat_id: str, user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == uuid.UUID(chat_id),
            ChatMember.user_id == uuid.UUID(user_id),
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise ChatError("You are not a member", status_code=404)

    await db.delete(member)
    await db.commit()


async def add_member(chat_id: str, user_id: str, new_user_id: str, db: AsyncSession) -> Chat:
    chat = await get_chat(chat_id, user_id, db)

    if chat.type == "direct":
        raise ChatError("Cannot add members to direct chat")

    member = next((m for m in chat.members if str(m.user_id) == user_id), None)
    if not member or member.role not in ("owner", "admin"):
        raise ChatError("Not enough permissions", status_code=403)

    already = any(str(m.user_id) == new_user_id for m in chat.members)
    if already:
        raise ChatError("User already in chat")

    result = await db.execute(select(User).where(User.id == uuid.UUID(new_user_id)))
    if not result.scalar_one_or_none():
        raise ChatError("User not found", status_code=404)

    db.add(ChatMember(chat_id=uuid.UUID(chat_id), user_id=uuid.UUID(new_user_id), role="member"))
    await db.commit()

    result = await db.execute(
        select(Chat)
        .where(Chat.id == uuid.UUID(chat_id))
        .options(selectinload(Chat.members).selectinload(ChatMember.user))
    )
    return result.scalar_one()
