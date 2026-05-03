from fastapi import WebSocket, WebSocketDisconnect
from typing import DefaultDict
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# peer_id -> WebSocket
active_connections: DefaultDict[str, dict] = defaultdict(dict)
# room_id -> set(peer_id)
rooms: DefaultDict[str, set] = defaultdict(set)


async def handle_connection(websocket: WebSocket, room_id: str, peer_id: str):
    await websocket.accept()

    active_connections[peer_id] = websocket
    rooms[room_id].add(peer_id)

    # 1. Говорим новому пиру его собственный id
    await websocket.send_json({
        "type": "self-id",
        "peerId": peer_id
    })

    # 2. Говорим новому пиру кто УЖЕ был в комнате (отдельное сообщение!)
    existing_peers = list(rooms[room_id] - {peer_id})
    await websocket.send_json({
        "type": "room-state",
        "peers": existing_peers
    })

    # 3. Говорим всем ОСТАЛЬНЫМ что новый участник вошёл
    await broadcast_to_room(room_id, {
        "type": "peer-joined",
        "peerId": peer_id,
    }, exclude=peer_id)

    logger.info(f"Peer {peer_id} joined room {room_id}, existing: {existing_peers}")

    try:
        while True:
            data = await websocket.receive_json()
            await route_message(room_id, peer_id, data)
    except WebSocketDisconnect:
        await cleanup(room_id, peer_id)


async def route_message(room_id: str, sender_id: str, data: dict):
    msg_type = data.get("type")
    target_id = data.get("targetId")

    # Адресные сообщения: offer, answer, ice-candidate
    if target_id and target_id in active_connections:
        await active_connections[target_id].send_json({
            **data,
            "fromId": sender_id
        })
        return

    # Широковещательные: chat, mute, raise-hand
    if msg_type in ("chat", "mute", "raise-hand"):
        await broadcast_to_room(room_id, {**data, "fromId": sender_id}, exclude=sender_id)


async def broadcast_to_room(room_id: str, message: dict, exclude: str = None):
    peers = rooms[room_id] - ({exclude} if exclude else set())
    for peer_id in list(peers):
        if peer_id in active_connections:
            try:
                await active_connections[peer_id].send_json(message)
            except Exception:
                await cleanup(room_id, peer_id)


async def cleanup(room_id: str, peer_id: str):
    active_connections.pop(peer_id, None)
    rooms[room_id].discard(peer_id)

    if not rooms[room_id]:
        del rooms[room_id]

    await broadcast_to_room(room_id, {
        "type": "peer-left",
        "peerId": peer_id
    })
    logger.info(f"Peer {peer_id} left room {room_id}")
