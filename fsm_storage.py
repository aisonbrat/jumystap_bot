"""
PostgreSQL-backed FSM storage for aiogram 3 (Supabase-compatible).

Reads state + data in one query and caches per storage_key to cut DB round-trips.
"""
import json
from typing import Any, Dict, Optional, Tuple, cast

import asyncpg

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import (
    BaseStorage,
    DefaultKeyBuilder,
    KeyBuilder,
    StateType,
    StorageKey,
)


class PostgreSQLStorage(BaseStorage):
    def __init__(
        self,
        pool: asyncpg.Pool,
        key_builder: Optional[KeyBuilder] = None,
    ) -> None:
        self.pool = pool
        self.key_builder = key_builder or DefaultKeyBuilder()
        self._row_cache: Dict[str, Tuple[Optional[str], Dict[str, Any]]] = {}

    def _base_key(self, key: StorageKey) -> str:
        return self.key_builder.build(key)

    def _invalidate(self, storage_key: str) -> None:
        self._row_cache.pop(storage_key, None)

    def _parse_data(self, raw: Any) -> Dict[str, Any]:
        if raw is None:
            return {}
        if isinstance(raw, str):
            return json.loads(raw)
        return dict(raw)

    async def _fetch_row(
        self, storage_key: str,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        cached = self._row_cache.get(storage_key)
        if cached is not None:
            return cached

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state, data FROM fsm_states WHERE storage_key = $1",
                storage_key,
            )

        if row is None:
            result: Tuple[Optional[str], Dict[str, Any]] = (None, {})
        else:
            result = (row["state"], self._parse_data(row["data"]))

        self._row_cache[storage_key] = result
        return result

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        storage_key = self._base_key(key)
        state_value: Optional[str]
        if state is None:
            state_value = None
        else:
            state_value = cast(str, state.state if isinstance(state, State) else state)

        async with self.pool.acquire() as conn:
            if state_value is None:
                row = await conn.fetchrow(
                    "SELECT data FROM fsm_states WHERE storage_key = $1",
                    storage_key,
                )
                if row is None or not row["data"]:
                    await conn.execute(
                        "DELETE FROM fsm_states WHERE storage_key = $1",
                        storage_key,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE fsm_states
                        SET state = NULL, updated_at = NOW()
                        WHERE storage_key = $1
                        """,
                        storage_key,
                    )
            else:
                await conn.execute(
                    """
                    INSERT INTO fsm_states (storage_key, state)
                    VALUES ($1, $2)
                    ON CONFLICT (storage_key) DO UPDATE
                        SET state = EXCLUDED.state, updated_at = NOW()
                    """,
                    storage_key,
                    state_value,
                )

        self._invalidate(storage_key)

    async def get_state(self, key: StorageKey) -> Optional[str]:
        storage_key = self._base_key(key)
        state, _ = await self._fetch_row(storage_key)
        return state

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        storage_key = self._base_key(key)
        payload = json.dumps(data)

        async with self.pool.acquire() as conn:
            if not data:
                row = await conn.fetchrow(
                    "SELECT state FROM fsm_states WHERE storage_key = $1",
                    storage_key,
                )
                if row is None or row["state"] is None:
                    await conn.execute(
                        "DELETE FROM fsm_states WHERE storage_key = $1",
                        storage_key,
                    )
                else:
                    await conn.execute(
                        """
                        UPDATE fsm_states
                        SET data = '{}'::jsonb, updated_at = NOW()
                        WHERE storage_key = $1
                        """,
                        storage_key,
                    )
            else:
                await conn.execute(
                    """
                    INSERT INTO fsm_states (storage_key, data)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (storage_key) DO UPDATE
                        SET data = EXCLUDED.data, updated_at = NOW()
                    """,
                    storage_key,
                    payload,
                )

        self._invalidate(storage_key)

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        storage_key = self._base_key(key)
        _, data = await self._fetch_row(storage_key)
        return data.copy()

    async def close(self) -> None:
        self._row_cache.clear()
