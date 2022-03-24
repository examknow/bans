import json
from aiosqlite  import connect as db_connect
from dataclasses import dataclass
from typing      import List, Optional, Any
from .common     import DBTable

@dataclass
class ConfigItem(object):
    key: str
    value: str

class ChannelConfigItem(ConfigItem):
    channel: int

class BotConfigTable(DBTable):
    async def get(self,
            key: str):

        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT value
                FROM bot_config
                WHERE key = ?
            """, [key])

            res = await cursor.fetchone()
            if res:
                return json.loads(res[0])

    async def set(self,
            key: str,
            value: Any):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                INSERT OR REPLACE
                INTO bot_config
                (key, value)
                VALUES
                (?, ?)
            """, [key, json.dumps(value)])
            await db.commit()

    async def delete(self,
            key: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                DELETE FROM bot_config
                WHERE key = ?
            """, [key])
            await db.commit()

class ChannelConfigTable(DBTable):
    async def get(self,
            channel_id: int,
            key: str):

        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT value
                FROM channel_config
                WHERE channel_id = ?
                AND key = ?
            """, [channel_id, key])

            res = await cursor.fetchone()
            if res:
                return json.loads(res[0])

    async def set(self,
            channel_id: int,
            key: str,
            value: Any):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                INSERT OR REPLACE
                INTO channel_config
                (channel_id, key, value)
                VALUES
                (?, ?, ?)
            """, [channel_id, key, json.dumps(value)])
            await db.commit()

    async def delete(self,
            channel_id: int,
            key: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                DELETE FROM channel_config
                WHERE channel_id = ?
                AND key = ?
            """, [channel_id, key])
            await db.commit()
