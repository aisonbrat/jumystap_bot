"""
aiogram FSM storage backed by Upstash Redis REST API.
"""
import json
from typing import Any, Dict, Optional, cast

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import (
    BaseStorage,
    DefaultKeyBuilder,
    KeyBuilder,
    StateType,
    StorageKey,
)
from upstash_redis.asyncio import Redis


class UpstashStorage(BaseStorage):
    def __init__(
        self,
        redis: Redis,
        key_builder: Optional[KeyBuilder] = None,
    ) -> None:
        self.redis = redis
        self.key_builder = key_builder or DefaultKeyBuilder()
        # Per-user cache for the current warm instance (avoids duplicate REST calls).
        self._state_cache: Dict[str, Optional[str]] = {}
        self._data_cache: Dict[str, Dict[str, Any]] = {}

    def _storage_id(self, key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.destiny}"

    def _key(self, key: StorageKey, part: str) -> str:
        return self.key_builder.build(key, cast(Any, part))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        sid = self._storage_id(key)
        redis_key = self._key(key, "state")
        if state is None:
            await self.redis.delete(redis_key)
            self._state_cache.pop(sid, None)
            return
        value = cast(str, state.state if isinstance(state, State) else state)
        await self.redis.set(redis_key, value)
        self._state_cache[sid] = value

    async def get_state(self, key: StorageKey) -> Optional[str]:
        sid = self._storage_id(key)
        if sid in self._state_cache:
            return self._state_cache[sid]
        value = await self.redis.get(self._key(key, "state"))
        self._state_cache[sid] = value
        return value

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        sid = self._storage_id(key)
        redis_key = self._key(key, "data")
        if not data:
            await self.redis.delete(redis_key)
            self._data_cache.pop(sid, None)
            return
        await self.redis.set(redis_key, json.dumps(data))
        self._data_cache[sid] = dict(data)

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        sid = self._storage_id(key)
        if sid in self._data_cache:
            return dict(self._data_cache[sid])
        raw = await self.redis.get(self._key(key, "data"))
        if not raw:
            data: Dict[str, Any] = {}
        elif isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = dict(raw)
        self._data_cache[sid] = data
        return dict(data)

    async def close(self) -> None:
        pass
