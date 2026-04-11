import json
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections[user_id].add(ws)

    def disconnect(self, user_id: str, ws: WebSocket) -> None:
        self._connections[user_id].discard(ws)
        if not self._connections[user_id]:
            del self._connections[user_id]

    async def send_to_user(self, user_id: str, payload: dict) -> None:
        dead = set()
        for ws in self._connections.get(user_id, set()):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def broadcast_to_users(self, user_ids: list[str], payload: dict) -> None:
        for user_id in user_ids:
            await self.send_to_user(user_id, payload)

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))


ws_manager = WebSocketManager()
