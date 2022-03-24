from aiosqlite  import connect as db_connect
from dataclasses import dataclass
from typing      import List, Optional
from .common     import DBTable

@dataclass
class DBChannel(object):
    id: int
    name: str
    autojoin: bool

class ChannelsTable(DBTable):
    async def add(self,
            name: str) -> int:

        async with db_connect(self._db_location) as db:
            await db.execute("""
                INSERT INTO channels
                (name, autojoin)
                VALUES (?, 1)
            """, [name])
            await db.commit()

            cursor = await db.execute("""
                SELECT id
                FROM channels
                ORDER BY id DESC
                LIMIT 1
            """)
            return (await cursor.fetchone())[0]

    async def get(self,
            name: str) -> Optional[DBChannel]:

        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT id, name, autojoin
                FROM channels
                WHERE name = ?
                LIMIT 1""", [name])

            res = await cursor.fetchone()
            if res:
                return DBChannel(*res)
            else:
                return None

    async def from_id(self, id: int) -> Optional[DBChannel]:
        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT id, name, autojoin
                FROM channels
                WHERE id = ?
                LIMIT 1""", [id])

            res = await cursor.fetchone()
            if len(res) > 0:
                return DBChannel(*res)
            else:
                return None

    async def list(self, join: bool = True) -> Optional[List[DBChannel]]:

        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT id, name, autojoin
                FROM channels
                WHERE autojoin = ?""", [int(join)])

            res = await cursor.fetchall()
            return [DBChannel(*row) for row in res]

    async def set_autojoin(self,
            id: int,
            join: bool):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                UPDATE channels
                SET autojoin = ?
                WHERE id = ?
            """, [join, id])
            await db.commit()
