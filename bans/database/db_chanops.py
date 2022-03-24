from aiosqlite  import connect as db_connect
from time        import time
from typing      import List, Optional, Tuple
from .common     import DBTable

class ChanOpsTable(DBTable):
    async def add(self,
            channel: int,
            account: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                INSERT INTO chanops
                (channel_id, account)
                VALUES (?, ?)
            """, [channel, account])
            await db.commit()

            cursor = await db.execute("""
                SELECT id
                FROM chanops
                ORDER BY id DESC
                LIMIT 1
            """)
            return (await cursor.fetchone())[0]

    async def remove(self,
            channel: int,
            account: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                DELETE FROM chanops
                WHERE channel_id = ?
                AND account = ?
            """, [channel, account])
            await db.commit()

    async def is_chanop(self, channel: int, account: str) -> bool:
        query = """
            SELECT id
            FROM chanops
            WHERE channel_id = ?
            AND account = ?
        """
        async with db_connect(self._db_location) as db:
            cursor = await db.execute(query, [channel, account])
            return bool(await cursor.fetchall())
