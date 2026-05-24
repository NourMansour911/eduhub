import hashlib
import json
from typing import Any, Dict, List, Optional

import redis.asyncio as redis

from dtos.redis_session_dto import RedisSessionDTO
from helpers.logger import get_logger

logger = get_logger(__name__)


class RedisProvider:
    def __init__(self, url: str):
        self.url = url
        self.client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        self.client = redis.Redis.from_url(
            url=self.url,
            decode_responses=True,
        )
        logger.info("[REDIS CONNECT SUCCESS]")

    async def disconnect(self) -> None:
        if self.client:
            await self.client.close()
        self.client = None

    def _ensure_client(self) -> redis.Redis:
        if self.client is None:
            raise RuntimeError("Redis client is not connected")
        return self.client

    def hash_value(self, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    async def get(self, key: str) -> Optional[str]:
        return await self._ensure_client().get(key)

    async def set(self, key: str, value: str) -> None:
        await self._ensure_client().set(key, value)

    async def delete(self, key: str) -> None:
        await self._ensure_client().delete(key)

    async def hset(self, key: str, mapping: Dict[str, Any]) -> None:
        await self._ensure_client().hset(key, mapping=mapping)

    async def hgetall(self, key: str) -> Dict[str, Any]:
        return await self._ensure_client().hgetall(key)

    async def push(self, key: str, value: str) -> None:
        await self._ensure_client().rpush(key, value)

    async def pop(self, key: str) -> Optional[str]:
        return await self._ensure_client().lpop(key)

    async def get_list(self, key: str) -> List[str]:
        return await self._ensure_client().lrange(key, 0, -1)

    async def add_to_set(self, key: str, value: str) -> None:
        await self._ensure_client().sadd(key, value)

    async def get_set(self, key: str) -> List[str]:
        return list(await self._ensure_client().smembers(key))

    def build_collection_key(self, user_id: str, session_id: str) -> str:
        return f"user:{user_id}:session:{session_id}"

    def build_session_key(self, user_id: str, session_id: str) -> str:
        return self.build_collection_key(user_id=user_id, session_id=session_id)

    async def get_collection(self, user_id: str, session_id: str) -> Optional[RedisSessionDTO]:
        key = self.build_collection_key(user_id=user_id, session_id=session_id)
        raw_value = await self.get(key)
        if raw_value is None:
            return None
        return RedisSessionDTO.model_validate(json.loads(raw_value))

    async def save_collection(self, collection: RedisSessionDTO, session_id: str) -> None:
        key = self.build_collection_key(user_id=collection.user_id, session_id=session_id)
        payload = json.dumps(collection.model_dump())
        await self.set(key, payload)

    async def append_message(
        self,
        user_id: str,
        session_id: str,
        message: Dict[str, Any],
    ) -> RedisSessionDTO:
        collection = await self.get_collection(user_id=user_id, session_id=session_id)
        if collection is None:
            collection = RedisSessionDTO(user_id=user_id)

        collection.messages.append(message)
        await self.save_collection(collection, session_id=session_id)
        return collection

    async def replace_messages(
        self,
        user_id: str,
        session_id: str,
        messages: List[Dict[str, Any]],
    ) -> RedisSessionDTO:
        collection = await self.get_collection(user_id=user_id, session_id=session_id)
        if collection is None:
            collection = RedisSessionDTO(user_id=user_id)

        collection.messages = messages
        await self.save_collection(collection, session_id=session_id)
        return collection

    async def get_messages(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        collection = await self.get_collection(user_id=user_id, session_id=session_id)
        if collection is None:
            return []
        return collection.messages

    async def get_last_messages(
        self,
        user_id: str,
        session_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        collection = await self.get_collection(user_id=user_id, session_id=session_id)
        if collection is None or limit <= 0:
            return []

        return collection.messages[-limit:]


    async def get_cache(self, key: str) -> Optional[str]:
        return await self.get(key)

    async def set_cache(self, key: str, value: str) -> None:
        await self.set(key, value)

    async def list_collections(self) -> List[str]:
        pattern = "user:*:session:*"
        keys = await self._ensure_client().keys(pattern)

        collections = set()
        for key in keys:
            parts = key.split(":")
            if len(parts) >= 4:
                collections.add(f"{parts[0]}:{parts[1]}:{parts[2]}:{parts[3]}")
        return list(collections)

    async def clear_all_collections(self) -> None:
        keys = await self._ensure_client().keys("*")
        if keys:
            await self._ensure_client().delete(*keys)
            logger.info(f"Deleted {len(keys)} keys from Redis")

    async def clear_user_sessions(self, user_id: str) -> None:
        pattern = f"user:{user_id}:session:*"
        keys = await self._ensure_client().keys(pattern)
        if keys:
            await self._ensure_client().delete(*keys)
            logger.info(f"Deleted {len(keys)} keys for user {user_id}")

    async def clear_session_collection(self, user_id: str, session_id: str) -> None:
        key = self.build_collection_key(user_id=user_id, session_id=session_id)
        await self.delete(key)