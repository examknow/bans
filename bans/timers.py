import asyncio

from ircrobots import Bot
from time      import time

from .database import Database

async def check_expiry(bot: Bot, db: Database):
    while True:
        now  = int(time())
        wait = 10.0

        if not bot.servers:
            await asyncio.sleep(wait)
            continue

        server = list(bot.servers.values())[0]

        expired = await db.bans.get_expired()
        expired_groups = {}
        for ban in expired:
            if not ban.channelid in expired_groups:
                expired_groups[ban.channelid] = []

            expired_groups[ban.channelid].append(ban)

        for channelid, bans in expired_groups.items():
            channel = (await db.channels.from_id(channelid)).name
            if not channel in server.channels:
                continue

            args = []
            modes = ""
            for ban in bans:
                modes += ban.mode
                if ban.mask is not None:
                    args.append(ban.mask)

            await server._remove_modes(channel, modes, args)
        await asyncio.sleep(wait)
