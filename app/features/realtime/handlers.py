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

    elif event_type == "message.delete":
        await _handle_delete(user_id, event)

    elif event_type == "call.invite":
        await _handle_call_invite(user_id, event)

    elif event_type == "call.accept":
        await _handle_call_accept(user_id, event)

    elif event_type == "call.reject":
        await _handle_call_reject(user_id, event)

    elif event_type == "call.end":
        await _handle_call_end(user_id, event)

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
            await websocket.send_text(json.dumps({"error": e.message, "status_code": e.status_code}))

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

async def _handle_delete(user_id: str, event: dict) -> None:
    from app.features.messages import service as msg_service
    from app.features.messages.models import Message
    from app.features.chats.models import ChatMember
    from sqlalchemy import select
    import uuid

    message_id = event.get("message_id")
    if not message_id:
        return

    async with AsyncSessionLocal() as db:
        try:
            await msg_service.delete_for_all(message_id, user_id, db)

            result = await db.execute(select(Message).where(Message.id == uuid.UUID(message_id)))
            msg = result.scalar_one_or_none()
            if not msg:
                return

            result = await db.execute(
                select(ChatMember).where(ChatMember.chat_id == msg.chat_id)
            )
            member_ids = [str(m.user_id) for m in result.scalars().all()]

            payload = {
                "type": "message.deleted",
                "message_id": message_id,
            }
            await ws_manager.broadcast_to_users(member_ids, payload)

        except Exception:
            pass


async def _handle_call_invite(user_id: str, event: dict) -> None:
    """
    Инициатор звонка отправляет:
    { type: "call.invite", chat_id: "...", room_id: "...", callee_id: "..." }
    Сервер пересылает вызываемому уведомление с данными для подключения.
    """
    callee_id = event.get("callee_id")
    room_id = event.get("room_id")
    chat_id = event.get("chat_id")
    caller_name = event.get("caller_name", "")

    if not callee_id or not room_id:
        return

    await ws_manager.send_to_user(callee_id, {
        "type": "call.incoming",
        "room_id": room_id,
        "chat_id": chat_id,
        "caller_id": user_id,
        "caller_name": caller_name,
    })


async def _handle_call_accept(user_id: str, event: dict) -> None:
    """
    Вызываемый принял звонок:
    { type: "call.accept", room_id: "...", caller_id: "..." }
    Сервер уведомляет инициатора что можно подключаться.
    """
    caller_id = event.get("caller_id")
    room_id = event.get("room_id")

    if not caller_id or not room_id:
        return

    await ws_manager.send_to_user(caller_id, {
        "type": "call.accepted",
        "room_id": room_id,
        "callee_id": user_id,
    })


async def _handle_call_reject(user_id: str, event: dict) -> None:
    """
    Вызываемый отклонил звонок:
    { type: "call.reject", room_id: "...", caller_id: "..." }
    """
    caller_id = event.get("caller_id")
    room_id = event.get("room_id")

    if not caller_id or not room_id:
        return

    await ws_manager.send_to_user(caller_id, {
        "type": "call.rejected",
        "room_id": room_id,
        "callee_id": user_id,
    })


async def _handle_call_end(user_id: str, event: dict) -> None:
    """
    Любой из участников завершил звонок:
    { type: "call.end", room_id: "...", peer_id: "..." }
    """
    peer_id = event.get("peer_id")
    room_id = event.get("room_id")

    if not peer_id or not room_id:
        return

    await ws_manager.send_to_user(peer_id, {
        "type": "call.ended",
        "room_id": room_id,
        "by_user_id": user_id,
    })
