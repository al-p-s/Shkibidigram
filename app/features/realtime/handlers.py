import json

from fastapi import WebSocket

from app.core.db import AsyncSessionLocal
from app.core.ws_manager import ws_manager
from app.features.messages.schemas import SendMessageRequest


async def handle_event(user_id: str, event: dict, websocket: WebSocket) -> None:
    event_type = event.get("type")

    if event_type == "ping":
        await websocket.send_text(json.dumps({"type": "pong"}))

    elif event_type == "message.send":
        await _handle_send_message(user_id, event, websocket)

    elif event_type == "message.read":
        await _handle_read(user_id, event)

    elif event_type == "typing":
        await _handle_typing(user_id, event)

    else:
        await websocket.send_text(json.dumps({"error": f"unknown event type: {event_type}"}))


async def _handle_send_message(user_id: str, event: dict, websocket: WebSocket) -> None:
    from app.features.messages import service as msg_service
    from app.features.messages.models import Message
    from app.features.chats.models import ChatMember
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    import uuid

    chat_id = event.get("chat_id")
    content = event.get("content")
    reply_to_id = event.get("reply_to_id")

    if not chat_id or not content:
        await websocket.send_text(json.dumps({"error": "chat_id and content required"}))
        return

    async with AsyncSessionLocal() as db:
        try:
            data = SendMessageRequest(
                content=content,
                type="text",
                reply_to_id=reply_to_id,
            )
            msg = await msg_service.send_message(chat_id, user_id, data, db)

            # Загружаем reply_to для получения текста оригинала
            result = await db.execute(
                select(Message)
                .where(Message.id == msg.id)
                .options(selectinload(Message.reply_to))
            )
            msg = result.scalar_one()

            result = await db.execute(
                select(ChatMember).where(ChatMember.chat_id == uuid.UUID(chat_id))
            )
            member_ids = [str(m.user_id) for m in result.scalars().all()]

            payload = {
                "type": "message.new",
                "message": {
                    "id": str(msg.id),
                    "chat_id": str(msg.chat_id),
                    "sender_id": str(msg.sender_id),
                    "content": msg.content,
                    "type": msg.type,
                    "reply_to_id": str(msg.reply_to_id) if msg.reply_to_id else None,
                    "reply_to_content": msg.reply_to.content if msg.reply_to else None,
                    "reply_to_sender_id": str(msg.reply_to.sender_id) if msg.reply_to else None,
                    "is_edited": msg.is_edited,
                    "created_at": msg.created_at.isoformat(),
                    "statuses": [],
                },
            }

            await ws_manager.broadcast_to_users(member_ids, payload)

        except msg_service.MessageError as e:
            await websocket.send_text(json.dumps({"error": e.message}))

async def _handle_read(user_id: str, event: dict) -> None:
    from app.features.messages import service as msg_service

    message_id = event.get("message_id")
    if not message_id:
        return

    async with AsyncSessionLocal() as db:
        try:
            await msg_service.mark_read(message_id, user_id, db)

            payload = {
                "type": "message.read",
                "message_id": message_id,
                "user_id": user_id,
            }

            from app.features.messages.models import Message
            from sqlalchemy import select
            result = await db.execute(select(Message).where(Message.id == message_id))  # type: ignore
            msg = result.scalar_one_or_none()
            if msg:
                await ws_manager.send_to_user(str(msg.sender_id), payload)

        except Exception:
            pass


async def _handle_typing(user_id: str, event: dict) -> None:
    chat_id = event.get("chat_id")
    if not chat_id:
        return

    from app.features.chats.models import ChatMember
    from sqlalchemy import select
    import uuid

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ChatMember).where(ChatMember.chat_id == uuid.UUID(chat_id))
        )
        member_ids = [str(m.user_id) for m in result.scalars().all() if str(m.user_id) != user_id]

    payload = {
        "type": "typing",
        "chat_id": chat_id,
        "user_id": user_id,
    }
    await ws_manager.broadcast_to_users(member_ids, payload)
