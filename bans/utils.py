import re, asyncio

from enum   import Enum, IntFlag
from typing import Optional, Set, List, Iterable, Tuple
from irctokens import build
from ircrobots import Server
from ircrobots.matching import Response, Folded, Nick, SELF, ANY
from ircstates.numerics import *

CHANSERV = Nick("ChanServ")
class ConfigError(Exception):
    pass

class SetOperator(Enum):
    ADD = "+"
    REM = "-"
    SET = "="

class SettingType(IntFlag):
    GLOBAL     = 1 # global value, only for admins
    CHANNEL    = 2 # channel value
    RESTRICTED = 4 # restricted to admins (only applies for channels)
    ANY        = GLOBAL|CHANNEL

async def cs_op(server: Server, channel: str) -> bool:
    await server.send(build(
        "CS", ["OP", channel]
    ))
    try:
        await server.wait_for(Response(
            "MODE", [Folded(channel), "+o", SELF], source=CHANSERV
        ), timeout=2)
    except asyncio.TimeoutError:
        return False
    else:
        return True

def is_admin(admins, mask) -> bool:
    for admin_mask in admins:
        if admin_mask.match(mask):
            return True
    return False

def mode_batches(
        chunk_n: int,
        add:     bool,
        modes:   str,
        args:    List[str]
        ) -> Iterable[Tuple[str, List[str]]]:

    mod = "+" if add else "-"
    for i in range(0, len(modes), chunk_n):
        cur_slice = slice(i, i+chunk_n)
        cur_modes = modes[cur_slice]
        cur_args  =  args[cur_slice]
        yield f"{mod}{modes[cur_slice]}", args[cur_slice]

async def try_join(server: Server, channel: str) -> bool:
    await server.send(build("JOIN", [channel]))
    try:
        while True:
            line = await server.wait_for({
                Response(RPL_ENDOFNAMES, [SELF, Folded(channel), ANY]),
                Response(ERR_BANNEDFROMCHAN, [ANY]),
                Response(ERR_INVITEONLYCHAN, [ANY]),
                Response(ERR_BADCHANNELKEY, [ANY]),
                Response(ERR_CHANNELISFULL, [ANY]),
                Response(ERR_NEEDREGGEDNICK, [ANY]),
                Response(ERR_THROTTLE, [ANY])
            }, timeout=5)

            if line.command == RPL_ENDOFNAMES:
                return True
            else:
                break
        return False
    except asyncio.TimeoutError:
        return False

SECONDS_MINUTES = 60
SECONDS_HOURS   = SECONDS_MINUTES*60
SECONDS_DAYS    = SECONDS_HOURS*24
SECONDS_WEEKS   = SECONDS_DAYS*7

def to_pretty_time(total_seconds: int) -> str:
    weeks, days      = divmod(total_seconds, SECONDS_WEEKS)
    days, hours      = divmod(days, SECONDS_DAYS)
    hours, minutes   = divmod(hours, SECONDS_HOURS)
    minutes, seconds = divmod(minutes, SECONDS_MINUTES)

    units = list(filter(
        lambda u: u[0] > 0,
        [
            (weeks,   "w"),
            (days,    "d"),
            (hours,   "h"),
            (minutes, "m"),
            (seconds, "s")
        ]
    ))
    out = ""
    for i, unit in units[:2]:
        out += f"{i}{unit}"
    return out

RE_PRETTYTIME = re.compile("^(?:(\d+)w)?(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
def from_pretty_time(s: str) -> Optional[int]:
    match = RE_PRETTYTIME.search(s)
    if match and match.group(0):
        seconds  = 0
        seconds += int(match.group(1) or "0") * SECONDS_WEEKS
        seconds += int(match.group(2) or "0") * SECONDS_DAYS
        seconds += int(match.group(3) or "0") * SECONDS_HOURS
        seconds += int(match.group(4) or "0") * SECONDS_MINUTES
        seconds += int(match.group(5) or "0")
        return seconds
    else:
        return None

def find_unescaped(s: str, c: Set[str]) -> List[int]:
    indexes: List[int] = []
    i = 0
    while i < len(s):
        c2 = s[i]
        if c2 == "\\":
            i += 1
        elif c2 in c:
            indexes.append(i)
        i += 1
    return indexes
