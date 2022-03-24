from enum   import Enum, IntFlag
from typing import List, Set, Any, Dict, Optional

from .database import Database
from .utils    import SettingType, SetOperator, ConfigError

class Setting(object):
    def __init__(self,
            default: Any,
            type: SettingType = SettingType.GLOBAL):
        self.default   = default
        self.type      = type
    def parse(self,
            current: Any,
            value:   str) -> Any:
        return self.format(value)
    def format(self, value: str) -> Any:
        return repr(value)

    def serialize(self, value: Any) -> Any:
        return value
    def deserialize(self, value: Any) -> Any:
        return value

    def pretty_print(self, value: Any) -> Any:
        return value

class SettingString(Setting):
    def format(self, value: str) -> Any:
        return value

class SettingBool(Setting):
    def format(self, value: str) -> bool:
        value = value.lower()
        if   value in {"on", "yes", "1", "true"}:
            return True
        elif value in {"off", "no", "0", "false"}:
            return False
        else:
            raise ConfigError("value not 'on' or 'off'")

class SettingInt(Setting):
    def format(self, value: str) -> int:
        return int(value)

class SettingFloat(Setting):
    def format(self, value: str) -> float:
        return float(value)

class SettingSet(Setting):
    def parse(self,
            current: Set[str],
            value:   str
            ) -> List[str]:

        current = current.copy()
        op      = value[:1]

        if value[:1] in {o.name for o in SetOperator}:
            items = set(value[1:].split(","))
            if   op == SetOperator.ADD:
                current |= items
            elif op == SetOperator.REM:
                current -= items
            elif op == SetOperator.SET:
                current  = items
        else:
            current = set(value.split(",")) # default to SET if no op given

        return current

    # json doesnt like sets :[
    def serialize(self, value: Set[str]) -> List[str]:
        return list(value)
    def deserialize(self, value: List[str]) -> Set[str]:
        return set(value)

    def pretty_print(self, value: Set[str]) -> str:
        return ", ".join(value)

class SettingEnum(SettingSet):
    def __init__(self,
            default: Any,
            options: Set[str],
            type: SettingType = SettingType.GLOBAL):
        self._options = options
        super().__init__(default, type)

    def parse(self,
            current: Set[str],
            value:   str
            ) -> Set[str]:

        base    = super().parse(current, value)
        unknown = list(sorted(base-self._options))

        if unknown:
            raise ConfigError(f"unknown value '{unknown[0]}'")
        else:
            return base


class RuntimePreferences(object):
    def __init__(self, db: Database):
        self.db: Database = db
        self.settings: Dict[str, Any] = {
            "reportChannel": SettingString(None, type=SettingType.ANY|SettingType.RESTRICTED),
            "autoExpire": SettingInt(0, type=SettingType.CHANNEL),
            "reportOn": SettingEnum(
                {},
                {"new", "exp", "rem"},
                type=SettingType.CHANNEL
            ),
        }

    async def get(self,
            key: str,
            channel: Optional[str] = None,
            privileged: Optional[bool] = True):

        if not key in self.settings.keys():
            raise ConfigError(f"{key} is not a valid preference")

        if (self.settings[key].type & SettingType.RESTRICTED and
            not privileged):

            raise ConfigError(f"{key} is restricted and cannot be managed by non-privileged users.")

        if not channel:
            # global config
            if not self.settings[key].type & SettingType.GLOBAL:
                raise ConfigError(f"{key} is not valid in the global context")
            if (ret := await self.db.config.bot.get(key)) is not None:
                return ret
        elif (channel := await self.db.channels.get(channel)) is not None:
            if not self.settings[key].type & SettingType.CHANNEL:
                raise ConfigError(f"{key} is not valid in the channel context")
            if (ret := await self.db.config.channel.get(channel.id, key)) is not None:
                return self.settings[key].deserialize(ret)

        return self.settings[key].default

    async def get_pretty(self,
            key: str,
            channel: Optional[str] = None,
            privileged: Optional[bool] = True):

        ret = await self.get(key, channel, privileged)
        return self.settings[key].pretty_print(ret)

    async def set(self,
            key: str,
            value: Any,
            channel: Optional[str] = None,
            privileged: Optional[bool] = True):

        if not key in self.settings.keys():
            raise ConfigError(f"{key} is not a valid preference")

        if (self.settings[key].type & SettingType.RESTRICTED and
            not privileged):

            raise ConfigError(f"{key} is restricted and cannot be managed by non-privileged users.")

        try:
            validated = self.settings[key].parse(await self.get(key, channel=channel, privileged=privileged), value)
        except Exception as e:
            raise ConfigError(f"Invalid value data: {e}")

        if not channel:
            if not self.settings[key].type & SettingType.GLOBAL:
                raise ConfigError(f"{key} is not valid in the global context")
            await self.db.config.bot.set(key, validated)
        elif (channel := await self.db.channels.get(channel)) is not None:
            if not self.settings[key].type & SettingType.CHANNEL:
                raise ConfigError(f"{key} is not valid in the channel context")
            serialized = self.settings[key].serialize(validated)
            await self.db.config.channel.set(channel.id, key, serialized)

    async def unset(self,
            key: str,
            channel: Optional[str] = None):

        if not key in self.settings.keys():
            raise ConfigError(f"{key} is not a valid preference")

        if not channel:
            await self.db.config.bot.delete(key)
        elif (channel := await self.db.channels.get(channel)) is not None:
            await self.db.config.channel.delete(channel.id, key)
