from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage

from redis.asyncio import Redis


def create_fsm_storage(redis_url: str) -> RedisStorage:
    redis = Redis.from_url(redis_url, decode_responses=True)
    return RedisStorage(
        redis=redis,
        key_builder=DefaultKeyBuilder(prefix="customer_bot:fsm"),
    )
