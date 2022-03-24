from aiosqlite  import connect as db_connect
from time        import time
from dataclasses import dataclass
from typing      import List, Optional
from .common     import DBTable

@dataclass
class DBComment(object):
    by_mask: str
    by_account: Optional[str]
    ts: int
    comment: str

class CommentsTable(DBTable):
    async def add(self,
            id: int,
            by_mask: str,
            by_account: Optional[str],
            comment: str):

        async with db_connect(self._db_location) as db:
            await db.execute("""
                INSERT INTO comments
                (ban_id, by_mask, by_account, time, comment)
                VALUES (?, ?, ?, ?, ?)
            """, [id, by_mask, by_account, int(time()), comment])
            await db.commit()

    async def get(self, id: int) -> List[DBComment]:
        async with db_connect(self._db_location) as db:
            cursor = await db.execute("""
                SELECT by_mask, by_account, time, comment
                FROM comments
                WHERE ban_id = ?
                ORDER BY time ASC
            """, [id])
            return [DBComment(*row) for row in await cursor.fetchall()]
