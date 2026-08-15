import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.core.ws_manager import ws_manager
from app.features.realtime.handlers import handle_event
from app.features.realtime.online import set_offline, set_online

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    user_id = decode_token(token)
    if not user_id:
        await websocket.close(code=4001)
        return

    await ws_manager.connect(user_id, websocket)
    await set_online(user_id)
    await _broadcast_presence(user_id, online=True)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
                await handle_event(user_id, event, websocket)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "invalid json"}))
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, websocket)
        await set_offline(user_id)
        await _broadcast_presence(user_id, online=False)


async def _broadcast_presence(user_id: str, online: bool) -> None:
    from app.core.db import AsyncSessionLocal
    from app.features.contacts.models import Contact
    from sqlalchemy import select
    import uuid

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Contact.owner_id).where(Contact.contact_id == uuid.UUID(user_id))
        )
        contact_owner_ids = [str(row) for row in result.scalars().all()]

    payload = {
        "type": "presence",
        "user_id": user_id,
        "online": online,
    }
    await ws_manager.broadcast_to_users(contact_owner_ids, payload)
