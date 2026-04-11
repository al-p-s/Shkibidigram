import redis.asyncio as aioredis

from app.config import settings

redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    return redis_client


async def init_redis() -> None:
    global redis_client
    redis_client = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )


async def close_redis() -> None:
    if redis_client:
        await redis_client.aclose()
