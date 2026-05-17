from fastapi import APIRouter, WebSocket, Query, Depends
from fastapi.responses import HTMLResponse
import uuid

from app.core.dependencies import get_current_user
from app.features.users.models import User
from app.features.calls.signaling import handle_connection

router = APIRouter(tags=["calls"])


@router.post("/rooms")
async def create_room(current_user: User = Depends(get_current_user)):
    """Создать комнату для звонка. Возвращает room_id."""
    return {"roomId": str(uuid.uuid4())[:8]}


@router.get("/test", response_class=HTMLResponse)
async def test_page():
    return '<meta http-equiv="refresh" content="0; url=/static/index.html">'


@router.websocket("/ws/{room_id}")
async def ws_endpoint(
    websocket: WebSocket,
    room_id: str,
    peer_id: str = Query(default=None),
):
    if not peer_id:
        peer_id = str(uuid.uuid4())[:8]
    await handle_connection(websocket, room_id, peer_id)
