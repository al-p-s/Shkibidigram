import redis.asyncio as redis
from app.config import settings  # ← берём url из конфига, не хардкодим

r: redis.Redis = None


async def get_redis():
    global r
    if r is None:
        r = redis.from_url(settings.redis_url, decode_responses=True)
    return r


async def add_peer_to_room(room_id: str, peer_id: str):
    client = await get_redis()
    await client.sadd(f"room:{room_id}:peers", peer_id)
    await client.expire(f"room:{room_id}:peers", 3600)


async def remove_peer_from_room(room_id: str, peer_id: str):
    client = await get_redis()
    await client.srem(f"room:{room_id}:peers", peer_id)


async def get_peers_in_room(room_id: str) -> list[str]:
    client = await get_redis()
    return list(await client.smembers(f"room:{room_id}:peers"))
