from app.core.redis import redis_client

ONLINE_KEY = "online:{user_id}"
ONLINE_TTL = 60  # SEX (секунд)


async def set_online(user_id: str) -> None:
    await redis_client.setex(ONLINE_KEY.format(user_id=user_id), ONLINE_TTL, "1")


async def set_offline(user_id: str) -> None:
    await redis_client.delete(ONLINE_KEY.format(user_id=user_id))


async def is_online(user_id: str) -> bool:
    return bool(await redis_client.exists(ONLINE_KEY.format(user_id=user_id)))


async def get_online_statuses(user_ids: list[str]) -> dict[str, bool]:
    return {uid: await is_online(uid) for uid in user_ids}
