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

    def _key(self, key: StorageKey, part: str) -> str:
        return self.key_builder.build(key, cast(Any, part))

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        redis_key = self._key(key, "state")
        if state is None:
            await self.redis.delete(redis_key)
            return
        value = cast(str, state.state if isinstance(state, State) else state)
        await self.redis.set(redis_key, value)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return await self.redis.get(self._key(key, "state"))

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        redis_key = self._key(key, "data")
        if not data:
            await self.redis.delete(redis_key)
            return
        await self.redis.set(redis_key, json.dumps(data))

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        raw = await self.redis.get(self._key(key, "data"))
        if not raw:
            return {}
        if isinstance(raw, str):
            return json.loads(raw)
        return dict(raw)

    async def close(self) -> None:
        pass
