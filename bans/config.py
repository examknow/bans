import yaml

from dataclasses    import dataclass
from os.path        import expanduser
from re             import compile as re_compile
from typing         import Dict, List, Optional, Pattern, Tuple
from ircrobots.glob import Glob, compile as glob_compile

from .runtime    import RuntimePreferences
from .database   import Database

@dataclass
class Config(object):
    server:   Tuple[str, int, bool]
    nickname: str
    username: str
    realname: str
    password: Optional[str]
    admins: List[Glob]
    database: str
    runtime: RuntimePreferences

    sasl: Optional[Tuple[str, str]]

def load(filepath: str):
    with open(filepath) as file:
        config_yaml = yaml.safe_load(file.read())

    nickname = config_yaml["nickname"]

    server   = config_yaml["server"]
    hostname, port_s = server.split(":", 1)
    tls      = False

    if port_s.startswith("+"):
        tls    = True
        port_s = port_s.lstrip("+")
    port = int(port_s)

    if "sasl" in config_yaml:
        sasl = (config_yaml["sasl"]["username"], config_yaml["sasl"]["password"])
    else:
        sasl = None
    db = Database(expanduser(config_yaml["database"]))

    return Config(
        (hostname, port, tls),
        nickname,
        config_yaml.get("username", nickname),
        config_yaml.get("realname", nickname),
        config_yaml.get("password", None),
        [glob_compile(m) for m in config_yaml["admins"]],
        db,
        RuntimePreferences(db),
        sasl
    )
