import asyncio
from argparse import ArgumentParser

from ircrobots import ConnectionParams, SASLUserPass

from .         import Bot
from .config   import Config, load as config_load
from .database import Database
from .timers   import check_expiry

async def main(config: Config):
    db  = config.database
    bot = Bot(config, db)

    host, port, tls      = config.server

    params = ConnectionParams(
        config.nickname,
        host,
        port,
        tls,
        username=config.username,
        realname=config.realname,
        password=config.password,
        autojoin=[c.name for c in await db.channels.list()]
    )
    if config.sasl is not None:
        sasl_user, sasl_pass = config.sasl
        params.sasl = SASLUserPass(sasl_user, sasl_pass)
    await bot.add_server(host, params)
    await asyncio.gather(
        bot.run(),
        check_expiry(bot, db)
    )

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("config")
    args   = parser.parse_args()

    config = config_load(args.config)
    asyncio.run(main(config))
