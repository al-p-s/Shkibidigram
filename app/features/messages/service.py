import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.features.chats.models import ChatMember
from app.features.messages.models import (
    Attachment,
    Message,
    MessageDeletedFor,
    MessageStatus,
)
from app.features.messages.schemas import EditMessageRequest, SendMessageRequest


class MessageError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code


async def _load_message(message_id: uuid.UUID, db: AsyncSession) -> Message:
    result = await db.execute(
        select(Message)
        .where(Message.id == message_id)
        .options(
            selectinload(Message.attachments),
            selectinload(Message.statuses),
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise MessageError("Message not found", status_code=404)
    return msg


async def _check_member(chat_id: uuid.UUID, user_id: uuid.UUID, db: AsyncSession) -> ChatMember:
    result = await db.execute(
        select(ChatMember).where(
            ChatMember.chat_id == chat_id,
            ChatMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise MessageError("Not a chat member", status_code=403)
    return member


async def get_messages(
    chat_id: str,
    user_id: str,
    limit: int,
    before_id: str | None,
    db: AsyncSession,
) -> list[Message]:
    await _check_member(uuid.UUID(chat_id), uuid.UUID(user_id), db)

    query = (
        select(Message)
        .where(
            Message.chat_id == uuid.UUID(chat_id),
            Message.is_deleted_for_all == False,  # noqa
        )
        .options(
            selectinload(Message.attachments),
            selectinload(Message.statuses),
        )
        .order_by(Message.created_at.desc())
        .limit(limit)
    )

    if before_id:
        pivot = await _load_message(uuid.UUID(before_id), db)
        query = query.where(Message.created_at < pivot.created_at)

    result = await db.execute(query)
    messages = list(result.scalars().all())

    deleted_ids = await _get_deleted_ids(uuid.UUID(user_id), [m.id for m in messages], db)
    return [m for m in messages if m.id not in deleted_ids]


async def _get_deleted_ids(user_id: uuid.UUID, message_ids: list[uuid.UUID], db: AsyncSession) -> set[uuid.UUID]:
    if not message_ids:
        return set()
    result = await db.execute(
        select(MessageDeletedFor.message_id).where(
            MessageDeletedFor.user_id == user_id,
            MessageDeletedFor.message_id.in_(message_ids),
        )
    )
    return set(result.scalars().all())


async def send_message(
    chat_id: str,
    user_id: str,
    data: SendMessageRequest,
    db: AsyncSession,
) -> Message:
    await _check_member(uuid.UUID(chat_id), uuid.UUID(user_id), db)

    if data.reply_to_id:
        result = await db.execute(
            select(Message).where(
                Message.id == data.reply_to_id,
                Message.chat_id == uuid.UUID(chat_id),
            )
        )
        if not result.scalar_one_or_none():
            raise MessageError("Reply target not found in this chat")

    msg = Message(
        chat_id=uuid.UUID(chat_id),
        sender_id=uuid.UUID(user_id),
        type=data.type,
        content=data.content,
        reply_to_id=data.reply_to_id,
    )
    db.add(msg)
    await db.flush()

    members_result = await db.execute(
        select(ChatMember).where(ChatMember.chat_id == uuid.UUID(chat_id))
    )
    for member in members_result.scalars().all():
        if str(member.user_id) != user_id:
            db.add(MessageStatus(
                message_id=msg.id,
                user_id=member.user_id,
                status="delivered",
            ))

    await db.commit()
    return await _load_message(msg.id, db)


async def edit_message(
    message_id: str,
    user_id: str,
    data: EditMessageRequest,
    db: AsyncSession,
) -> Message:
    msg = await _load_message(uuid.UUID(message_id), db)

    if str(msg.sender_id) != user_id:
        raise MessageError("Not your message", status_code=403)

    if msg.is_deleted_for_all:
        raise MessageError("Message deleted")

    age = datetime.now(timezone.utc) - msg.created_at.replace(tzinfo=timezone.utc)
    if age.total_seconds() > 86400:
        raise MessageError("Edit window expired")

    msg.content = data.content
    msg.is_edited = True
    await db.commit()
    return await _load_message(msg.id, db)


async def delete_for_all(message_id: str, user_id: str, db: AsyncSession) -> None:
    msg = await _load_message(uuid.UUID(message_id), db)

    if str(msg.sender_id) != user_id:
        raise MessageError("Not your message", status_code=403)

    msg.is_deleted_for_all = True
    await db.commit()


async def delete_for_me(message_id: str, user_id: str, db: AsyncSession) -> None:
    msg = await _load_message(uuid.UUID(message_id), db)

    existing = await db.execute(
        select(MessageDeletedFor).where(
            MessageDeletedFor.message_id == uuid.UUID(message_id),
            MessageDeletedFor.user_id == uuid.UUID(user_id),
        )
    )
    if existing.scalar_one_or_none():
        return

    db.add(MessageDeletedFor(
        message_id=uuid.UUID(message_id),
        user_id=uuid.UUID(user_id),
    ))
    await db.commit()


async def mark_read(message_id: str, user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(MessageStatus).where(
            MessageStatus.message_id == uuid.UUID(message_id),
            MessageStatus.user_id == uuid.UUID(user_id),
        )
    )
    status = result.scalar_one_or_none()
    if status:
        status.status = "read"
        status.updated_at = datetime.now(timezone.utc)
        await db.commit()
