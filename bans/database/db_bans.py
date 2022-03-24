from aiosqlite  import connect as db_connect
from time        import time
from typing      import List, Optional
from dataclasses import dataclass
from .common     import DBTable

@dataclass
class DBBan(object):
    id: int
    channelid: int
    setter: str
    mode: str
    ts: int
    mask: Optional[int]
    expiry: Optional[int]
    removed: Optional[int]
    remover: Optional[str]
    reason: Optional[str]

class BansTable(DBTable):
    async def add(self,
            channel: int,
            setter: str,
            mode:   str,
            mask:   Optional[str] = None,
            expiry: Optional[int] = None,
            reason: Optional[str] = None):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                INSERT INTO bans
                (channel_id, setter, mode, mask, ts, expiry_ts, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, [channel, setter, mode, mask, int(time()), expiry, reason])
            await db.commit()

            cursor = await db.execute("""
                SELECT id
                FROM bans
                ORDER BY id DESC
                LIMIT 1
            """)
            return (await cursor.fetchone())[0]

    async def _get(self,
            where: str,
            limit: Optional[int],
            *args: str) -> List[DBBan]:

        async with db_connect(self._db_location) as db:
            limit_str = ""
            if limit is not None:
                limit_str = f"LIMIT {limit}"

            query = f"""
                SELECT id, channel_id, setter, mode, ts, mask, expiry_ts, remove_ts, remover, reason
                FROM bans
                {where}
                {limit_str}
            """

            cursor = await db.execute(query, args)
            rows = await cursor.fetchall()
            return [DBBan(*row) for row in rows]

    async def get_by_id(self,
            id: int) -> List[DBBan]:

        try:
            return (await self._get("WHERE id = ?", 1, id))[0]
        except IndexError:
            return None

    async def get_by_channel(self,
            channel: int,
            by_active: Optional[bool] = None,
            by_setter: Optional[str] = None,
            limit: Optional[int] = 10) -> List[DBBan]:

        args: List[str] = []
        where = "WHERE channel_id = ?"
        args.append(channel)
        if by_active is not None:
            where += by_active == True and " AND remove_ts IS NULL" or " AND remove_ts IS NOT NULL"
        if by_setter is not None:
            where += f" AND setter LIKE ?"
            args.append(by_setter)
        return await self._get(where, limit, *args)

    async def get_expired(self) -> List[DBBan]:

        return await self._get("WHERE expiry_ts < ? AND remove_ts IS NULL", None, int(time()))

    async def get_id(self,
            channel: str,
            mask: str) -> Optional[DBBan]:

        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT id
                FROM bans
                WHERE remove_ts IS NULL
                ORDER BY id DESC
                LIMIT 1""")

            res = await cursor.fetchone()
            if len(res) > 0:
                return res[0]
            else:
                return None

    async def set_reason(self,
            id: int,
            reason: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                UPDATE bans
                SET reason = ?
                WHERE id = ?""", [reason, id])
            await db.commit()

    async def set_expiry(self,
            id: int,
            expiry: Optional[int]):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                UPDATE bans
                SET expiry_ts = ?
                WHERE id = ?""", [expiry, id])
            await db.commit()

    async def set_reason(self,
            id: int,
            reason: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                UPDATE bans
                SET reason = ?
                WHERE id = ?""", [reason, id])
            await db.commit()

    async def remove(self,
            id: int,
            remover: Optional[str] = None):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                UPDATE bans
                SET remove_ts = ?, remover = ?
                WHERE id = ?""", [int(time()), remover, id])
            await db.commit()
