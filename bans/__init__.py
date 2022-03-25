import asyncio, traceback
from dataclasses import dataclass
from datetime    import datetime
from time        import time
from typing      import Any, Dict, List, Optional, Tuple, Set

from irctokens import build, Line, Hostmask
from ircrobots import Bot as BaseBot
from ircrobots import Server as BaseServer

from ircstates.numerics   import *
from ircrobots.matching   import Responses, Response, ANY, Folded, SELF

from .config           import Config
from .database         import Database
from .utils            import (to_pretty_time, from_pretty_time, mode_batches, cs_op,
                                SettingType, ConfigError, is_admin, try_join)
from .database.db_bans import DBBan

@dataclass
class Caller(object):
    source: str
    nick: str
    account: Optional[str]

# decorator, for command usage strings
def usage(usage_string: str):
    def usage_inner(object: Any):
        if not hasattr(object, "_usage"):
            object._usage: List[str] = []
        # decorators eval bottom up, insert to re-invert order
        object._usage.insert(0, usage_string)
        return object
    return usage_inner

class UsageError(Exception):
    pass

class Server(BaseServer):
    def __init__(self,
            bot:      BaseBot,
            name:     str,
            config:   Config,
            database: Database):

        super().__init__(bot, name)
        self.config   = config
        self.db       = database

    def set_throttle(self, rate: int, time: float):
        # turn off throttling
        pass

    async def report(self, msg: str, channel: Optional[str] = None):
        if channel is not None:
            if (report_channel := await self.config.runtime.get("reportChannel")):
                await self.send(build("PRIVMSG", [report_channel, msg]))
        else:
            if (report_channel := await self.config.runtime.get("reportChannel")):
                await self.send(build("PRIVMSG", [report_channel, msg]))

    async def _request_comment(self, ban_id: int):
        if (ban := await self.db.bans.get_by_id(ban_id)) is not None:
            nick = ban.setter.split("!")[0]
            chan = await self.db.channels.get(ban.channelid)
            out  = (f"Please comment on action "
                    f"#{ban.id} ({chan} +{ban.mode}{ban.mask and ' ' + ban.mask})"
                    f" (/msg {self.nickname} comment {ban.id} +1w trolling)")
            await self.send(build("NOTICE", [nick, out]))

    async def _is_authorized(self, ban: DBBan, caller: Caller):

        # only the ban setter and known channel ops can do things
        # with bans
        if is_admin(self.config.admins, caller.source):
            return True
        elif self.casefold(ban.setter) == self.casefold(caller.source):
            return True
        elif (caller.account is not None and
            await self.db.chanops.is_chanop(ban.channelid, caller.account)):
            return True
        return False

    async def _populate_modes(self, channel, modes: str):
        await self.send(build("MODE", [channel.name, f"+{modes}"]))

        waiting = len(modes)

        masks: Set[Tuple[str, str, str]] = set()
        while True:
            line = await self.wait_for(Responses({
                RPL_BANLIST, RPL_ENDOFBANLIST,
                RPL_QUIETLIST, RPL_ENDOFQUIETLIST
            }, [ANY, Folded(channel.name)]))
            if line.command in [RPL_ENDOFBANLIST, RPL_ENDOFQUIETLIST]:
                waiting -= 1
                if waiting == 0:
                    break
            else:
                # :server 367 * #c mask set-by set-at
                # :server 728 * q #c mask set-by set-at
                offset = 0
                type = "b"
                if line.command == RPL_QUIETLIST:
                    offset += 1
                    type = "q"

                mask   = line.params[offset+2]
                set_by = line.params[offset+3]
                set_at = int(line.params[offset+4])
                masks.add((type, mask, set_by))

        old_db    = await self.db.bans.get_by_channel(channel.id, by_active=True, limit=None)
        old_masks = {(b.mode, b.mask) for b in old_db}
        masks_l   = {(m[0], m[1]) for m in masks}

        for mode, mask in old_masks:
            if (mode, mask) in masks:
                continue
            if (id := await self.db.bans.get_id(channel.id, mask)) is not None:
                await self.db.bans.remove(id, None)

        for mode, mask, setter in masks:
            if (mode, mask) in old_masks:
                continue
            await self.db.bans.add(
                channel.id,
                setter,
                mode,
                mask
            )

    async def _remove_modes(self, channel: str, modes: str, args: List[str]):
        cuser = self.channels[self.casefold(channel)].users[self.nickname_lower]
        remove_op = False
        if not "o" in cuser.modes:
            await cs_op(self, channel)
            remove_op = True
        if remove_op:
            modes += "o"
            args.append(self.nickname)

        batches = mode_batches(
            self.isupport.modes, False, modes, args
        )
        for b_modes, b_args in batches:
            await self.send(build("MODE", [channel, b_modes]+b_args))

    def _time_format(self, ts: int):
        now = int(time())
        if now > ts:
            # 2021-10-21T17:29:10 (1m5s ago)
            prettyts = f"{to_pretty_time(int(now-ts))} ago"
        else:
            # 2021-10-21T17:29:10 (1m5s from now)
            prettyts = f"{to_pretty_time(int(ts-now))} from now"
        tss = datetime.utcfromtimestamp(ts).isoformat()
        return f"\x02{tss}\x02 ({prettyts})"

    async def _action_format(self, ban: DBBan):
        if not (channel := await self.db.channels.from_id(ban.channelid)):
            # none of this matters if the channel isn't real
            return (
                    "Something has gone horribly wrong."
                    " Please report this to the bot admin."
            )
        ts = self._time_format(ban.ts)
        mask = ban.mask is not None and f" {ban.mask}" or ""
        out = (
                f"#{ban.id} ({channel.name} +{ban.mode}{mask})"
                f" was set by \x02{ban.setter}\x02 at {ts}"
        )

        if ban.reason is not None:
            out += f" with the reason: \x1d{ban.reason}\x1d"

        if ban.expiry is not None:
            exts = self._time_format(ban.expiry)
            out += f" and had an expiry time of {exts}"

        if ban.removed is not None:
            rmts = self._time_format(ban.removed)
            rmvr = ban.remover is not None and ban.remover or "(unknown)"
            out += f". It was removed on {rmts} by \x02{rmvr}\x02"
        out += "."

        return out

    async def line_read(self, line: Line):
        if (line.command == "PRIVMSG" and
                not self.is_me(line.hostmask.nickname) and
                self.is_me(line.params[0])):

            cmd, _, args = line.params[1].partition(" ")
            await self.cmd(line.hostmask, cmd, args, line.tags)

        elif (line.command == "JOIN" and
                self.is_me(line.hostmask.nickname)):

            if not (channel := await self.db.channels.get(self.casefold(line.params[0]))):
                # we only care about channels in our database
                return
            await self._populate_modes(channel, "bq")

        elif (line.command == "MODE" and
                not self.is_me(line.params[0])):

            if not (channel := await self.db.channels.get(self.casefold(line.params[0]))):
                # we only care about channels in our database
                return
            if not channel.name in self.channels.keys():
                # idk when this would happen but just in case
                return

            if (line.tags is not None and
                "account" in line.tags and
                not await self.db.chanops.is_chanop(channel.id, self.casefold(line.tags["account"]))):

                # if this is a new chanop account, save it
                await self.db.chanops.add(channel.id, self.casefold(line.tags["account"]))

            args = line.params[2:]
            added: List[Tuple[str, str]] = []
            removed: List[Tuple[str, str]] = []
            adding = False
            for c in str(line.params[1]):
                if c == "+":
                    adding = True
                elif c == "-":
                    adding = False
                elif c in {"b", "q", "e", "I"} and len(args) > 0:
                    if adding:
                        added.append((c, args.pop(0)))
                    else:
                        removed.append((c, args.pop(0)))

            for mode, mask in added:
                id = await self.db.bans.add(channel.id, line.source, mode, mask)
                await self._request_comment(id)
                if (default_duration := await self.config.runtime.get("autoExpire", channel=channel.name)) > 0:
                    await self.db.bans.set_expiry(id, int(time())+default_duration)
            for mode, mask in removed:
                if (id := await self.db.bans.get_id(channel.id, mask)) is not None:
                    await self.db.bans.remove(id, line.source)

    async def cmd(self,
            hostmask: Hostmask,
            command:  str,
            args:     str,
            tags:    Optional[Dict[str, str]]):

        attrib  = f"cmd_{command}"
        if hasattr(self, attrib):
            account = None
            if tags is not None and "account" in tags:
                account = tags["account"]
            caller = Caller(str(hostmask), hostmask.nickname, account)
            func   = getattr(self, attrib)
            outs: List[str] = []
            try:
                outs.extend(await func(caller, args))
            except UsageError as e:
                outs.append(str(e))
                for usage in func._usage:
                    outs.append(f"usage: {command.upper()} {usage}")

            for out in outs:
               await self.send(build("NOTICE", [hostmask.nickname, out]))
        else:
            err = f"\x02{command.upper()}\x02 is not a valid command"
            await self.send(build("NOTICE", [hostmask.nickname, err]))

    @usage("<expr>")
    async def cmd_eval(self, caller: Caller, sargs: str) -> List[str]:
        return [repr(await eval(sargs))]

    @usage("[channel] <setting> <value>")
    async def cmd_config(self, caller: Caller, sargs: str) -> List[str]:
        args = sargs.split(None, 3)
        if not args:
            raise UsageError("Not enough parameters")

        privileged = is_admin(self.config.admins, caller.source)
        print(privileged)
        channel = None
        if args[0].startswith("#") and len(args) > 1:
            channel = self.casefold(args[0])
            if not (c := await self.db.channels.get(channel)):
                return [f"{channel} is not a valid channel name"]
            if ((caller.account is None or
                    not await self.db.chanops.is_chanop(c.id, caller.account)) and
                    not privileged):

                return ["Permission denied"]
            del args[0]

        key   = args.pop(0)
        value = None
        if len(args) > 0:
            value = " ".join(args)

        try:
            if value is not None:
                await self.config.runtime.set(key, value, channel=channel, privileged=privileged)
                return ["done!"]
            else:
                ret = await self.config.runtime.get_pretty(key, channel=channel, privileged=privileged)
                return [f"{key} = {ret}"]
        except ConfigError as e:
            traceback.print_exc()
            return [f"Error: {e}"]

    @usage("<id>")
    async def cmd_info(self, caller: Caller, sargs: str) -> List[str]:
        args = sargs.split(None, 1)
        if not args:
            raise UsageError("Please provide an id")
        elif not args[0].isdigit():
            raise UsageError("That's not a number")

        if ((ban := await self.db.bans.get_by_id(int(args[0]))) is not None and
            await self._is_authorized(ban, caller)):
            ret = [await self._action_format(ban)]
            if (comments := await self.db.comments.get(int(args[0]))):
                ret.append("\x02comments:\x02")
                for comment in comments:
                    if comment.by_account is not None:
                        who = f"{comment.by_mask} ({comment.by_account})"
                    else:
                        who = comment.by_mask
                    tss = datetime.utcfromtimestamp(comment.ts).isoformat()
                    ret.append(
                        f" {tss}"
                        f" by \x02{who}\x02:"
                        f" {comment.comment}"
                    )
            return ret
        else:
            return [f"#{args[0]} does not exist or you do not have permission to see it"]

    @usage("<id>|^ [+time] [reason]")
    async def cmd_comment(self, caller: Caller, sargs: str) -> List[str]:
        args = sargs.split(None, 3)
        if not args:
            raise UsageError("Please provide an id")
        elif not args[0].isdigit() and args[0][0] != "^":
            raise UsageError("id must be a number")

        if args[0][0] == "^":
            ids = [b.id for b in
                   await self.db.bans.get_last_by_setter(caller.source, len(args.pop(0)))]

            if not ids:
                return ["could not find any previous bans from you"]
        else:
            ids = [int(args.pop(0))]
        duration = None
        # should the ban duration start from the time of comment or ban placement
        # (~1d = 1 day from ban setting, +1d = 1 day from time of comment)
        relative_duration = False
        reason = None
        if args[0].startswith("+"):
            if (duration := from_pretty_time(args[0][1:])) is None:
                return ["invalid time"]
            else:
                relative_duration = True
                del args[0]
        elif args[0].startswith("~"):
            if (duration := from_pretty_time(args[0][1:])) is None:
                return ["invalid time"]
            else:
                relative_duration = True
                del args[0]

        if len(args) > 0:
            reason = " ".join(args)

        for id in ids:
            if ((ban := await self.db.bans.get_by_id(id)) is not None and
                await self._is_authorized(ban, caller)):
                if ban.removed is not None:
                    return ["that ban is no longer active"]
                if duration is not None:
                    now = int(time())
                    if relative_duration:
                        duration += now
                    else:
                        if (ban.ts + now) < now:
                            return [f"#{id} would already have expired. Please set a longer duration."]
                        duration += ban.ts
                    await self.db.bans.set_expiry(id, duration)
                    log = f"set ban expiry to \x02{datetime.utcfromtimestamp(duration).isoformat()}\x02"
                    await self.db.comments.add(id, caller.source, caller.account, log)
                if reason is not None:
                    await self.db.bans.set_reason(id, reason)
                    log = f"set reason to \x1d{reason}\x1d"
                    await self.db.comments.add(id, caller.source, caller.account, log)
                return [f"#{id} has been commented"]
            else:
                return [f"#{id} does not exist or you do not have permission to modify it"]

    async def cmd_join(self, caller: Caller, sargs: str):
        args = sargs.split(None, 3)
        if not is_admin(self.config.admins, caller.source):
            return ["Permission denied"]
        elif not args:
            raise UsageError("Please provide a channel to join")

        if self.casefold(args[0]) in self.channels.keys():
            return [f"I'm already in {args[0]}"]

        if await try_join(self, args[0]):
            await self.db.channels.add(self.casefold(args[0]))
            await self.report(f"{caller.source} JOIN: \x02{args[0]}\x02")
            return [f"Successfully joined {args[0]}"]
        else:
            return [f"Failed to join {args[0]} - see the error log for more information"]

    async def cmd_part(self, caller: Caller, sargs: str):
        args = sargs.split(None, 3)
        if not is_admin(self.config.admins, caller.source):
            return ["Permission denied"]
        elif not args:
            raise UsageError("Please provide a channel to part")

        if not self.casefold(args[0]) in self.channels.keys():
            return [f"I'm not in {args[0]}"]

        if (db_channel := await self.db.channels.get(self.casefold(args[0]))) is not None:
            await self.db.channels.set_autojoin(db_channel.id, False)

        await self.send(build("PART", [args[0]]))
        await self.report(f"{caller.source} PART: \x02{args[0]}\x02")
        return [f"done!"]

    def line_preread(self, line: Line):
        print(f"< {line.format()}")
    def line_presend(self, line: Line):
        print(f"> {line.format()}")

class Bot(BaseBot):
    def __init__(self,
            config:   Config,
            database: Database):
        super().__init__()
        self.config   = config
        self._database = database

    def create_server(self, name: str):
        return Server(self, name, self.config, self._database)
